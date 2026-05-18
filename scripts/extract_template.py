"""
Extraction template — batch export AI chat conversations to Markdown.
Adapt the CONFIG section per platform before running.

Key features:
- Single browser tab (no tab explosion)
- Resume support (skip already-downloaded conversations)
- Timeout handling (long conversations fail gracefully)
- Duplicate filename detection (appends URL suffix)
- Image download with PerformanceObserver for signed URLs
"""
import json, subprocess, time, re, os, sys, urllib.request

# ============================================================
# CONFIG — adapt per platform
# ============================================================
BASE_URL = "https://www.doubao.com"                    # Platform base URL
OUTPUT_DIR = "output"                                   # Where to save .md files
IMG_DIR = os.path.join(OUTPUT_DIR, "images")            # Image storage
CONVERSATIONS_FILE = os.path.join(OUTPUT_DIR, "conversations.json")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")
API = "http://127.0.0.1:10086/command"
SESSION_NAME = "batch-extract"                          # WebBridge session
CURL_TIMEOUT = 300                                      # Seconds (increase for long conversations)

# DOM selectors — find with browser F12
MESSAGE_LIST_SELECTOR = "[class*=v_list_scroller]"      # Scrollable message container
MESSAGE_ITEM_SELECTOR = "[class*=inner-item]"           # Individual message
THINKING_SELECTOR = "[class*=thinking-box]"             # Thinking/reasoning section
IMAGE_WRAPPER_SELECTOR = "[class*=image-wrapper]"       # Lazy-load image wrappers
IMAGE_CDN_DOMAIN = "byteimg.com"                        # Image CDN (for PerformanceObserver)
AVATAR_DOMAIN_EXCLUDE = "avatar"                        # Exclude avatar images

# Role detection — adapt JS logic per platform
ROLE_DETECTION_JS = """
var hasBubble = html.indexOf("bg-g-send-msg-bubble-bg") > -1;
var hasCopyTelemetry = html.indexOf("data-copy-telemetry") > -1;
var hasJustifyEnd = html.indexOf("justify-end") > -1;
var role = (hasBubble || (!hasCopyTelemetry && hasJustifyEnd)) ? "user" : "ai";
"""
# ============================================================

_first_navigate = True

def curl_post(body_dict):
    body = json.dumps(body_dict)
    try:
        result = subprocess.run(
            ['curl', '-s', '-X', 'POST', API,
             '-H', 'Content-Type: application/json', '-d', body],
            capture_output=True, text=True, encoding='utf-8', timeout=CURL_TIMEOUT
        )
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except:
            return None
    except subprocess.TimeoutExpired:
        print("  [timeout]")
        return None
    except Exception as e:
        print(f"  [curl error] {e}")
        return None

def navigate(url):
    global _first_navigate
    new_tab = _first_navigate
    _first_navigate = False
    resp = curl_post({'action': 'navigate', 'args': {'url': url, 'newTab': new_tab}})
    if resp and resp.get('ok'):
        return resp.get('data', {}).get('success', False)
    return False

# The extract JS — inject CONFIG values for selectors
EXTRACT_JS = r"""
(async function(){
  var s = document.querySelector("MESSAGE_LIST_SELECTOR_PLACEHOLDER");
  if(!s) return JSON.stringify({err:"no scroller"});

  var perfUrls = [];
  var observer = null;
  try{
    observer = new PerformanceObserver(function(list){
      list.getEntries().forEach(function(e){
        if(e.name.indexOf("IMAGE_CDN_PLACEHOLDER") > -1 && e.name.indexOf("AVATAR_EXCLUDE_PLACEHOLDER") === -1){
          if(perfUrls.indexOf(e.name) === -1) perfUrls.push(e.name);
        }
      });
    });
    observer.observe({type: "resource", buffered: true});
  }catch(e){}

  // First pass: scroll to bottom to expand virtual list, then back to top
  var h = s.scrollHeight, c = s.clientHeight;
  for(var p=0; p<h+800; p+=Math.max(150, c-50)) s.scrollTop = p;
  await new Promise(function(r){setTimeout(r, 500);});
  s.scrollTop = 0;
  await new Promise(function(r){setTimeout(r, 2000);});

  function getBaseId(url){
    var m = url.match(/([0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
    return m ? m[1] : url.split("?")[0];
  }

  var items = s.querySelectorAll("MESSAGE_ITEM_SELECTOR_PLACEHOLDER");
  var messages = [];

  for(var i=0; i<items.length; i++){
    items[i].scrollIntoView({block:"center"});
    await new Promise(function(r){setTimeout(r, 1500);});

    // Scroll image wrappers to trigger lazy loading
    var wrappers = items[i].querySelectorAll("IMAGE_WRAPPER_SELECTOR_PLACEHOLDER");
    for(var w=0; w<wrappers.length; w++){
      wrappers[w].scrollIntoView({block:"center"});
      await new Promise(function(r){setTimeout(r, 1500);});
    }

    // Poll for image URLs
    var imgUrls = [];
    var hasPictures = items[i].querySelectorAll("picture").length > 0;
    var pollStart = Date.now();
    while(Date.now() - pollStart < 5000){
      var foundReal = false;
      items[i].querySelectorAll("source").forEach(function(src){
        var su = src.getAttribute("src") || src.getAttribute("srcset") || "";
        if(su && su.indexOf("IMAGE_CDN_PLACEHOLDER") > -1 && su.indexOf("data:") === -1){
          if(imgUrls.indexOf(su) === -1){ imgUrls.push(su); foundReal = true; }
        }
      });
      items[i].querySelectorAll("img").forEach(function(img){
        var su = img.currentSrc || img.src || "";
        if(su && su.indexOf("IMAGE_CDN_PLACEHOLDER") > -1 && su.indexOf("data:") === -1){
          if(imgUrls.indexOf(su) === -1){ imgUrls.push(su); foundReal = true; }
        }
      });
      if(foundReal) break;
      if(wrappers.length === 0 && !hasPictures && imgUrls.length === 0) break;
      await new Promise(function(r){setTimeout(r, 500);});
    }

    var html = items[i].innerHTML || "";
    var text = (items[i].textContent || "").trim();

    // ROLE DETECTION — platform-specific
    ROLE_DETECTION_JS_PLACEHOLDER

    // Thinking section
    var hasThinking = false, thinkingText = "";
    var clone = items[i].cloneNode(true);
    var thinkingBox = clone.querySelector("THINKING_SELECTOR_PLACEHOLDER");
    if(thinkingBox){
      hasThinking = true;
      thinkingText = (thinkingBox.textContent || "").trim();
      thinkingBox.remove();
    }

    // Clean clone: remove invisible elements and all img tags
    clone.querySelectorAll("[class*=invisible]").forEach(function(el){el.remove();});
    clone.querySelectorAll("img").forEach(function(img){img.remove();});

    // Match PerformanceObserver URLs to this message's images
    var matchedPerfUrls = [];
    var matchedBaseIds = [];
    imgUrls.forEach(function(srcUrl){
      var srcBase = srcUrl.split("?")[0];
      var srcId = getBaseId(srcUrl);
      if(matchedBaseIds.indexOf(srcId) === -1) matchedBaseIds.push(srcId);
      perfUrls.forEach(function(pUrl){
        if(matchedPerfUrls.indexOf(pUrl) === -1){
          var pBase = pUrl.split("?")[0];
          var pId = getBaseId(pUrl);
          if(pUrl.indexOf(srcBase) === 0 || srcBase.indexOf(pBase) === 0 || srcId === pId){
            matchedPerfUrls.push(pUrl);
          }
        }
      });
    });

    messages.push({
      index: i, role: role, hasThinking: hasThinking,
      thinkingText: thinkingText,
      html: clone.innerHTML,
      text: (clone.textContent || "").trim(),
      imgUrls: imgUrls,
      perfImgUrls: matchedPerfUrls
    });
  }

  if(observer) observer.disconnect();

  // Collect unmatched PerformanceObserver URLs
  var allMatchedIds = [];
  messages.forEach(function(m){
    m.imgUrls.forEach(function(u){ var id = getBaseId(u); if(allMatchedIds.indexOf(id) === -1) allMatchedIds.push(id); });
    m.perfImgUrls.forEach(function(u){ var id = getBaseId(u); if(allMatchedIds.indexOf(id) === -1) allMatchedIds.push(id); });
  });

  var unmatchedPerf = [], unmatchedIds = [];
  perfUrls.forEach(function(pUrl){
    var pId = getBaseId(pUrl);
    if(allMatchedIds.indexOf(pId) === -1 && unmatchedIds.indexOf(pId) === -1){
      unmatchedPerf.push(pUrl); unmatchedIds.push(pId);
    }
  });

  return JSON.stringify({
    success: true, messageCount: messages.length,
    messages: messages, unmatchedPerfUrls: unmatchedPerf
  });
})()
"""

# Inject CONFIG values into JS template
EXTRACT_JS = EXTRACT_JS.replace("MESSAGE_LIST_SELECTOR_PLACEHOLDER", MESSAGE_LIST_SELECTOR)
EXTRACT_JS = EXTRACT_JS.replace("MESSAGE_ITEM_SELECTOR_PLACEHOLDER", MESSAGE_ITEM_SELECTOR)
EXTRACT_JS = EXTRACT_JS.replace("IMAGE_WRAPPER_SELECTOR_PLACEHOLDER", IMAGE_WRAPPER_SELECTOR)
EXTRACT_JS = EXTRACT_JS.replace("IMAGE_CDN_PLACEHOLDER", IMAGE_CDN_DOMAIN)
EXTRACT_JS = EXTRACT_JS.replace("AVATAR_EXCLUDE_PLACEHOLDER", AVATAR_DOMAIN_EXCLUDE)
EXTRACT_JS = EXTRACT_JS.replace("THINKING_SELECTOR_PLACEHOLDER", THINKING_SELECTOR)
EXTRACT_JS = EXTRACT_JS.replace("ROLE_DETECTION_JS_PLACEHOLDER", ROLE_DETECTION_JS)

# ============================================================
# HTML → Markdown converter
# ============================================================
def html_to_markdown(html_text):
    text = html_text
    text = re.sub(r'<(?:script|style|svg)[^>]*>.*?</(?:script|style|svg)>', '', text, flags=re.DOTALL)
    for hi in range(6, 0, -1):
        text = re.sub(rf'<h{hi}[^>]*>(.*?)</h{hi}>',
                      lambda m, p='#'*hi: f'\n\n{p} {m.group(1).strip()}\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<(?:em|i)[^>]*>(.*?)</(?:em|i)>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\n\1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)

    def img_repl(m):
        src, alt = m.group(1) or '', m.group(2) or 'image'
        if src.startswith('data:'): return ''
        return f'![{alt}]({src})'
    text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>', img_repl, text)
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"[^>]*>',
                  lambda m: '' if m.group(2).startswith('data:') else f'![{m.group(1)}]({m.group(2)})', text)
    text = re.sub(r'<font[^>]*color="([^"]*)"[^>]*>(.*?)</font>', r'<span style="color:\1">\2</span>', text, flags=re.DOTALL)
    text = re.sub(r'</?font[^>]*>', '', text)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)
    text = re.sub(r'</?[ou]l[^>]*>', '\n', text)
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'\n```\n\1\n```\n', text, flags=re.DOTALL)

    def table_repl(m):
        content = m.group(1)
        content = re.sub(r'</?(?:thead|tbody|tfoot|colgroup)[^>]*>', '', content)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
        if not rows: return '\n'
        md_rows = []
        for row in rows:
            cells = re.findall(r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>', row, re.DOTALL)
            md_rows.append('|' + '|'.join(c.strip() for c in cells) + '|')
        if len(md_rows) >= 1:
            n = md_rows[0].count('|') - 1
            sep = '|' + '|'.join(['---'] * max(1, n)) + '|'
            return '\n\n' + md_rows[0] + '\n' + sep + '\n' + '\n'.join(md_rows[1:]) + '\n'
        return '\n\n' + '\n'.join(md_rows) + '\n'
    text = re.sub(r'<table[^>]*>(.*?)</table>', table_repl, text, flags=re.DOTALL)

    text = re.sub(r'<[^>]+>', '', text)
    for e, c in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&nbsp;',' '),('&#39;',"'"),('&#x27;',"'")]:
        text = text.replace(e, c)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()

# ============================================================
# Image downloader
# ============================================================
def download_image(url, conv_name, img_index):
    if not url or url.startswith('data:'):
        return None
    try:
        os.makedirs(IMG_DIR, exist_ok=True)
        safe_name = re.sub(r'[/\\:*?"<>|]', '_', conv_name)[:40]
        url_lower = url.lower()
        ext = '.png'
        if '.jpg' in url_lower or '.jpeg' in url_lower: ext = '.jpg'
        elif '.webp' in url_lower: ext = '.webp'
        elif '.gif' in url_lower: ext = '.gif'
        fname = f'{safe_name}_{img_index}{ext}'
        fpath = os.path.join(IMG_DIR, fname)
        if os.path.exists(fpath):
            return f'images/{fname}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': BASE_URL
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) > 200:
                with open(fpath, 'wb') as f:
                    f.write(data)
                return f'images/{fname}'
    except Exception as e:
        print(f"  [download err] {e}")
    return None

def sanitize(name):
    for ch in '/\\:*?"<>|':
        name = name.replace(ch, '_')
    return name[:120]

# ============================================================
# Core: extract a single conversation
# ============================================================
def extract_conversation(conv_title, conv_url):
    if not navigate(conv_url):
        return None, "navigate"
    time.sleep(8)

    resp = curl_post({'action': 'evaluate', 'args': {'code': EXTRACT_JS}})
    if not resp or not resp.get('ok'):
        return None, "evaluate"
    try:
        data = json.loads(resp['data']['value'])
    except:
        return None, "parse"
    if not data.get('success'):
        return None, data.get('err', 'unknown')

    messages = data.get('messages', [])
    if not messages:
        return None, "no messages"

    md_lines = [f'# {conv_title}', '', f'> 来源: {conv_url}', '', '---', '']
    img_counter = [0]
    downloaded_all = {}

    for msg in messages:
        role_label = '**[用户]**' if msg['role'] == 'user' else '**[AI]**'
        md_lines.append(f'### {role_label}')
        md_lines.append('')

        if msg.get('hasThinking'):
            think = msg.get('thinkingText', '')
            if think:
                md_lines.append('> [!NOTE]- 思考过程')
                for line in think.split('\n'):
                    if line.strip(): md_lines.append(f'> {line}')
                md_lines.append('')

        msg_md = html_to_markdown(msg['html'])

        download_urls = msg.get('perfImgUrls', [])
        if not download_urls:
            download_urls = msg.get('imgUrls', [])

        for img_url in download_urls:
            base_url = img_url.split('?')[0]
            if base_url in downloaded_all:
                local = downloaded_all[base_url]
                if local not in msg_md:
                    msg_md += f'\n\n![image]({local})'
                continue
            local = download_image(img_url, conv_title, img_counter[0])
            img_counter[0] += 1
            if local and base_url not in downloaded_all:
                downloaded_all[base_url] = local
                if local not in msg_md:
                    msg_md += f'\n\n![image]({local})'

        if msg_md:
            md_lines.append(msg_md)
        else:
            t = msg.get('text', '')
            if t: md_lines.append(t)
        md_lines.append(''); md_lines.append('---'); md_lines.append('')

    # Unmatched images
    unmatched = data.get('unmatchedPerfUrls', [])
    remaining = []
    for img_url in unmatched:
        base_url = img_url.split('?')[0]
        if base_url not in downloaded_all:
            local = download_image(img_url, conv_title, img_counter[0])
            img_counter[0] += 1
            if local:
                downloaded_all[base_url] = local
                remaining.append(local)
    if remaining:
        md_lines.append('### 其他图片')
        md_lines.append('')
        for lp in remaining:
            md_lines.append(f'![image]({lp})')
        md_lines.append('')

    return '\n'.join(md_lines), len(downloaded_all)

# ============================================================
# Progress management
# ============================================================
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed": [], "failed": [], "last_index": -1}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def get_existing_titles():
    existing = set()
    if not os.path.exists(OUTPUT_DIR):
        return existing
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith('.md'):
            existing.add(fname[:-3])
    return existing

# ============================================================
# Duplicate detection
# ============================================================
def find_collisions(conversations):
    """Return map of sanitized_name -> list of conversations (only where count > 1)"""
    name_map = {}
    for c in conversations:
        sn = sanitize(c['title'])
        if sn not in name_map:
            name_map[sn] = []
        name_map[sn].append(c)
    return {k: v for k, v in name_map.items() if len(v) > 1}

def make_unique_filename(conv, collisions, index_in_collision):
    """If title collides and this isn't the first, append chat ID suffix"""
    sn = sanitize(conv['title'])
    if sn in collisions:
        colliding_list = collisions[sn]
        # Find this conversation's position in the colliding list
        for i, c in enumerate(colliding_list):
            if c['href'] == conv['href'] and i > 0:
                chat_id = conv['href'].split('/')[-1]
                return f"{sn}_{chat_id[-6:]}"
    return sn

# ============================================================
# Main batch loop
# ============================================================
if __name__ == '__main__':
    with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
        all_convos = json.load(f)

    print(f"Total conversations: {len(all_convos)}")

    existing_titles = get_existing_titles()
    print(f"Already have .md files: {len(existing_titles)}")

    # Find collisions for unique naming
    collisions = find_collisions(all_convos)
    if collisions:
        dup_count = sum(len(v) for v in collisions.values())
        print(f"Duplicate filenames: {len(collisions)} groups, {dup_count} conversations")

    # Filter to unprocessed
    progress = load_progress()
    processed_urls = set(progress.get('processed', []))
    failed_urls = set(progress.get('failed', []))

    remaining = []
    collision_index = {}
    for c in all_convos:
        if c['href'] in processed_urls or c['href'] in failed_urls:
            continue
        sn = sanitize(c['title'])
        # For collision tracking
        if sn in collisions:
            if sn not in collision_index:
                collision_index[sn] = 0
            else:
                collision_index[sn] += 1
            idx = collision_index[sn]
        else:
            idx = 0
        # Check if this specific filename already exists
        unique_name = make_unique_filename(c, collisions, idx)
        if unique_name not in existing_titles or idx > 0:
            remaining.append(c)

    print(f"Remaining to process: {len(remaining)}")

    total_imgs = success = fail = 0

    for i, conv in enumerate(remaining):
        title = conv['title']
        url = BASE_URL + conv['href']

        print(f"\n[{i+1}/{len(remaining)}] {title}")
        sys.stdout.flush()

        md, img_cnt = extract_conversation(title, url)

        if md:
            # Generate unique filename
            sn = sanitize(title)
            if sn in collisions:
                coll_list = collisions[sn]
                for ci, c in enumerate(coll_list):
                    if c['href'] == conv['href'] and ci > 0:
                        sn = f"{sn}_{conv['href'].split('/')[-1][-6:]}"
                        break

            fpath = os.path.join(OUTPUT_DIR, f'{sn}.md')
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(md)
            print(f"  OK: {len(md)} chars, {img_cnt} images")
            total_imgs += img_cnt
            success += 1
            progress['processed'].append(conv['href'])
        else:
            print(f"  FAIL: {img_cnt}")
            fail += 1
            progress['failed'].append(conv['href'])

        if (success + fail) % 5 == 0:
            save_progress(progress)

    save_progress(progress)
    print(f"\n{'='*50}")
    print(f"Done! {success} success, {fail} fail, {total_imgs} total images")
    print(f"Total .md files: {len(get_existing_titles())}")
