import requests
import os

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

url = "https://api.github.com/repos/jaakkopasanen/AutoEq/contents/measurements/crinacle"

print(f"Token presente: {'SIM' if TOKEN else 'NAO'}")
print(f"URL: {url}")
print()

r = requests.get(url, headers=HEADERS)

print(f"Status: {r.status_code}")
print(f"Rate limit restante: {r.headers.get('X-RateLimit-Remaining', 'N/A')}")
print(f"Rate limit total: {r.headers.get('X-RateLimit-Limit', 'N/A')}")
print()

data = r.json()

if isinstance(data, list):
    print(f"Retornou lista com {len(data)} itens")
    for item in data[:10]:
        print(f"  {item['type']:6s}  {item['name']}")
elif isinstance(data, dict):
    print(f"Retornou dict:")
    print(f"  message: {data.get('message', 'N/A')}")
    print(f"  documentation_url: {data.get('documentation_url', 'N/A')}")
else:
    print(f"Tipo inesperado: {type(data)}")
    print(data)