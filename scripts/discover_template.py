"""
Discovery template — scroll sidebar to collect ALL conversation URLs.
Adapt the CONFIG section per platform before running.
"""
import json, subprocess, time, sys, os

# ============================================================
# CONFIG — adapt per platform
# ============================================================
CHAT_LIST_URL = "https://www.doubao.com/chat/"       # Platform main chat page
SIDEBAR_SCROLL_SELECTOR = "[class*=flow-scrollbar]"   # Scrollable sidebar container
LINK_MATCH_PATTERN = r"/chat/\d+"                     # Regex for conversation URLs (raw string!)
SESSION_NAME = "discover"                              # WebBridge session name
OUTPUT_FILE = "conversations.json"                     # Where to save URL list
API = "http://127.0.0.1:10086/command"
# ============================================================

def curl_post(body_dict):
    body = json.dumps(body_dict)
    result = subprocess.run(
        ['curl', '-s', '-X', 'POST', API,
         '-H', 'Content-Type: application/json', '-d', body],
        capture_output=True, text=True, encoding='utf-8', timeout=120
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except:
        return None

# The JS code auto-adapts via the CONFIG strings injected into it
DISCOVER_JS = f"""
(async function() {{
  var scroller = document.querySelector("{SIDEBAR_SCROLL_SELECTOR}");
  if (!scroller) return JSON.stringify({{err: "no scroller", selector: "{SIDEBAR_SCROLL_SELECTOR}"}});

  var seen = {{}};
  var allItems = [];
  var noNewCount = 0;

  for (var i = 0; i < 5000; i++) {{
    var links = scroller.querySelectorAll("a[href]");
    var newFound = 0;

    links.forEach(function(a) {{
      var h = a.getAttribute("href");
      var t = a.textContent.trim();
      if (h && h.match(/{LINK_MATCH_PATTERN}/) && !seen[h]) {{
        seen[h] = true;
        allItems.push({{title: t, href: h}});
        newFound++;
      }}
    }});

    if (newFound === 0) {{
      noNewCount++;
      if (noNewCount > 5) break;
    }} else {{
      noNewCount = 0;
    }}

    scroller.scrollTop = scroller.scrollHeight;
    await new Promise(function(r) {{ setTimeout(r, 1200); }});
  }}

  return JSON.stringify({{total: allItems.length, items: allItems}});
}})()
"""

if __name__ == '__main__':
    # Navigate to chat list
    resp = curl_post({'action': 'navigate', 'args': {'url': CHAT_LIST_URL, 'newTab': True}})
    if not resp or not resp.get('ok'):
        print("Navigation failed")
        sys.exit(1)

    print(f"Navigated to {CHAT_LIST_URL}, waiting for load...")
    time.sleep(6)

    # Run discovery
    resp = curl_post({'action': 'evaluate', 'args': {'code': DISCOVER_JS}})
    if not resp or not resp.get('ok'):
        print(f"Discovery failed: {resp}")
        sys.exit(1)

    data = json.loads(resp['data']['value'])
    if 'err' in data:
        print(f"JS error: {data['err']}")
        sys.exit(1)

    items = data.get('items', [])
    print(f"Discovered {len(items)} conversations")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

    if items:
        print(f"First: {items[0]['title']}")
        print(f"Last:  {items[-1]['title']}")
