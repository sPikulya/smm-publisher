import os
import re
import json
import urllib.parse
from datetime import datetime, timezone
import dateutil.parser
import requests
import frontmatter
from dotenv import load_dotenv

# Load environment variables
# Try loading from project root first (4 levels up from this script in .agents/skills/smm-publisher/scripts/)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..'))
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to current working directory

POSTS_DIR = os.getenv('POSTS_DIR', './')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '5'))

PLATFORM_CODES = {
    'Threads': 'th',
    'Instagram': 'inst',
    'Telegram': 'tg',
    'Facebook': 'fb',
    'LinkedIn': 'ln',
    'Google Business': 'gb'
}

def parse_n8n_response(response_text):
    """
    Parses the response from n8n to determine which networks succeeded.
    Example expected text:
    ✅ Telegram: Успішна
    ❌ Facebook: Не успішна - error
    🟡 Google Business: Створено, ще обробляється
    """
    successes = []
    
    for line in response_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Success is either ✅ or 🟡 (e.g. Google Business pending processing)
        is_success = line.startswith('✅') or line.startswith('🟡')
        
        if is_success:
            for plat_name, plat_code in PLATFORM_CODES.items():
                if f" {plat_name}:" in line:
                    successes.append(plat_code)
                    break
                    
    return successes

def get_file_path(uri):
    """Convert file:/// URI to local path, handling URL encoding."""
    if not uri:
        return None
    path = uri.replace('file://', '')
    return urllib.parse.unquote(path)

def process_file(filepath):
    print(f"Обробка файлу: {filepath}")
    try:
        post = frontmatter.load(filepath)
    except Exception as e:
        print(f"Помилка читання файлу {filepath}: {e}")
        return False

    status = post.get('status')
    if status not in ['ready', 'partial']:
        return False

    # Check publish date
    publish_date = post.get('publish_date')
    if publish_date:
        try:
            dt = dateutil.parser.parse(str(publish_date))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt > datetime.now(timezone.utc):
                print(f"Пропущено: publish_date {publish_date} в майбутньому.")
                return False
        except Exception as e:
            print(f"Помилка парсингу дати {publish_date}: {e}")

    # Determine target networks
    raw_networks = post.get('networks', '')
    networks = [n.strip() for n in raw_networks.split(',') if n.strip()]
    
    networks_success = post.get('networks_success', [])
    if not isinstance(networks_success, list):
        networks_success = []
        
    target_networks = [n for n in networks if n not in networks_success]
    
    if not target_networks:
        print("Немає цільових мереж для публікації. Оновлення статусу на published.")
        post['status'] = 'published'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        return True

    # Parse content for each network
    content_text = post.content
    content_pattern = re.compile(r'## Content:\s*([A-Za-z\s]+)\s*\n(.*?)(?=\n## Content:\s*[A-Za-z\s]+|\Z)', re.DOTALL)
    matches = content_pattern.findall(content_text)
    
    contents = {}
    for network, text in matches:
        contents[network.strip().lower()] = text.strip()

    # Prepare payload
    data_payload = {
        "id": post.get('id'),
        "net_list": target_networks,
        "content": contents
    }

    # Prepare files
    files = {}
    media_path = get_file_path(post.get('media'))
    media_ln_path = get_file_path(post.get('media_ln'))
    
    # Try relative to post file if not absolute and not found relative to CWD
    if media_path and not os.path.isabs(media_path) and not os.path.exists(media_path):
        post_dir = os.path.dirname(filepath)
        alt_path = os.path.join(post_dir, media_path)
        if os.path.exists(alt_path):
            media_path = alt_path

    if media_ln_path and not os.path.isabs(media_ln_path) and not os.path.exists(media_ln_path):
        post_dir = os.path.dirname(filepath)
        alt_path = os.path.join(post_dir, media_ln_path)
        if os.path.exists(alt_path):
            media_ln_path = alt_path

    open_files = []
    original_status = status
    try:
        if media_path and os.path.exists(media_path):
            f_media = open(media_path, 'rb')
            open_files.append(f_media)
            files['media_image'] = (os.path.basename(media_path), f_media)
            
        if media_ln_path and os.path.exists(media_ln_path):
            f_ln = open(media_ln_path, 'rb')
            open_files.append(f_ln)
            files['linkedin_image'] = (os.path.basename(media_ln_path), f_ln)

        # 1. Update status to 'processing' before HTTP request to avoid duplicate publications
        print(f"Зміна статусу на 'processing' перед надсиланням запиту: {filepath}")
        post['status'] = 'processing'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))

        print(f"Відправка до n8n: {target_networks}")
        response = requests.post(
            N8N_WEBHOOK_URL,
            data={"data": json.dumps(data_payload)},
            files=files if files else None,
            timeout=300  # 5 minutes timeout in case of long approvals
        )
        response.raise_for_status()
        
        resp_data = response.json()
        
        # Parse the webhook response
        if isinstance(resp_data, list) and len(resp_data) > 0:
            msg = resp_data[0].get('json', {}).get('message', '')
        elif isinstance(resp_data, dict):
            msg = resp_data.get('message', '')
        else:
            msg = str(resp_data)
            
        print(f"Відповідь від n8n:\n{msg}")
        
        new_successes = parse_n8n_response(msg)
        
        # 2. Any network requested but not marked as success (✅/🟡) in the response is a failure
        new_failures = [n for n in target_networks if n not in new_successes]
        
        # Update successful networks
        all_successes = list(set(networks_success + new_successes))
        
        post['networks_success'] = all_successes
        post['networks_failed'] = new_failures
        
        # Calculate final status
        if set(networks).issubset(set(all_successes)):
            post['status'] = 'published'
        else:
            post['status'] = 'partial'
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
            
        print(f"Файл {filepath} оновлено. Статус: {post['status']}")
        return True

    except Exception as e:
        print(f"Помилка відправки або обробки файлу {filepath}: {e}")
        # 3. Rollback: revert status back to original_status so it can be retried later
        try:
            print(f"Повернення статусу до '{original_status}' через збій")
            post['status'] = original_status
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
        except Exception as rollback_err:
            print(f"Не вдалося відкотити статус: {rollback_err}")
        return False
    finally:
        for f in open_files:
            f.close()

def main():
    if not N8N_WEBHOOK_URL:
        print("Помилка: N8N_WEBHOOK_URL не задано в .env")
        return

    processed = 0
    # Search for markdown files
    for root, _, files in os.walk(POSTS_DIR):
        for filename in files:
            if filename.endswith('.md'):
                filepath = os.path.join(root, filename)
                
                if process_file(filepath):
                    processed += 1
                    
                if processed >= BATCH_SIZE:
                    print(f"Досягнуто ліміт BATCH_SIZE ({BATCH_SIZE}). Завершення роботи.")
                    return

if __name__ == "__main__":
    main()
