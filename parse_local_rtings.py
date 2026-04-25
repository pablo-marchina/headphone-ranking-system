import re
import json
import os

def parse_local_xml_full():
    file_path = "rtings_pages.xml"
    
    if not os.path.exists(file_path):
        print(f"❌ Erro: O arquivo '{file_path}' não foi encontrado!")
        return

    print(f"📖 Lendo dados completos de {file_path}...")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Procura por TODOS os links na pasta de reviews de headphones
        links = re.findall(r'<loc>https://www\.rtings\.com/headphones/reviews/(.*?)</loc>', content)
        
        slugs = []
        for s in links:
            slug = s.strip('/')
            
            # FILTRO MÍNIMO: Só ignoramos o que for obviamente uma página de categoria
            # Ex: "best", "guides" ou a própria home de reviews.
            # Mantemos "wireless" e "gaming" pois muitos fones bons têm isso no nome.
            blacklist = ['best', 'guides', 'deals', 'test-results', 'recommendations']
            
            if slug and not any(b == slug or slug.startswith(b + '/') for b in blacklist):
                # Se o slug tiver pelo menos uma barra (marca/modelo), é quase certo que é um fone
                if '/' in slug:
                    slugs.append(slug)

        slugs = list(set(slugs)) # Remove duplicados

        os.makedirs('data', exist_ok=True)
        with open("data/rtings_library.json", "w", encoding="utf-8") as f:
            json.dump(slugs, f, indent=4, ensure_ascii=False)
        
        print(f"✅ SUCESSO RECUPERADO! {len(slugs)} fones extraídos do seu arquivo.")
        print("Agora sim, vamos para o mapeamento: python generate_mapping.py")

    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    parse_local_xml_full()