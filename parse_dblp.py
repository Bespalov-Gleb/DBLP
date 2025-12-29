import csv
import os
import urllib.request
import ssl
import gzip
from collections import defaultdict
from lxml import etree

DBLP_XML_URL = "https://drops.dagstuhl.de/storage/artifacts/dblp/xml/2025/dblp-2025-12-01.xml.gz"
DBLP_XML_URL_ALT = "https://dblp.org/xml/dblp.xml.gz"
LOCAL_XML_FILE = "dblp.xml"
LOCAL_XML_GZ_FILE = "dblp.xml.gz"
OUTPUT_DIR = "data"


def download_dblp_xml(url, output_file):
    """
    Загружает DBLP XML файл с указанного URL.
    
    Args:
        url: URL для загрузки файла
        output_file: путь для сохранения файла
    """
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        if file_size > 1000000:
            print(f"Файл {output_file} уже существует ({file_size/1024/1024:.2f} МБ)")
            return
        else:
            print(f"Файл {output_file} существует, но слишком мал ({file_size} байт). Перезагружаем...")
            os.remove(output_file)
    
    print(f"Загрузка DBLP XML с {url}...")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    request = urllib.request.Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0')
    request.add_header('Accept', 'application/xml, application/gzip, */*')
    
    try:
        with urllib.request.urlopen(request, context=ssl_context) as response:
            content = response.read()
            
            if content.startswith(b'<!DOCTYPE html') or content.startswith(b'<html'):
                print("ВНИМАНИЕ: Получен HTML вместо XML.")
                print("Пробуем альтернативный URL...")
                return download_dblp_xml(DBLP_XML_URL_ALT, output_file)
            
            is_gzip = content.startswith(b'\x1f\x8b')
            
            if is_gzip:
                print("Обнаружен gzip файл. Распаковка...")
                content = gzip.decompress(content)
                print(f"Распаковано: {len(content)/1024/1024:.2f} МБ")
            
            with open(output_file, 'wb') as out_file:
                out_file.write(content)
        print(f"Загрузка завершена: {output_file} ({len(content)/1024/1024:.2f} МБ)")
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        print("\nИНСТРУКЦИЯ ПО РУЧНОЙ ЗАГРУЗКЕ:")
        print("1. Скачайте файл вручную:")
        print("   - https://dblp.org/xml/dblp.xml.gz (сжатый, ~500 МБ)")
        print("   - или https://dblp.org/xml/dblp.xml (несжатый, ~2 ГБ)")
        print("2. Если скачали .gz файл, распакуйте его:")
        print("   - Windows: используйте 7-Zip или WinRAR")
        print("   - Linux/Mac: gunzip dblp.xml.gz")
        print("3. Поместите файл dblp.xml в текущую директорию")
        print("4. Запустите скрипт снова")
        raise


def normalize_author_name(name):
    """
    Нормализует имя автора.
    
    Args:
        name: исходное имя автора
    
    Returns:
        str: нормализованное имя или None
    """
    if not name:
        return None
    return name.strip()


def extract_venue(publication):
    """
    Извлекает место публикации (журнал или конференция).
    
    Args:
        publication: XML элемент публикации
    
    Returns:
        str: название журнала/конференции или "Unknown"
    """
    journal = publication.find("journal")
    booktitle = publication.find("booktitle")

    if journal is not None and journal.text:
        return journal.text.strip()
    elif booktitle is not None and booktitle.text:
        return booktitle.text.strip()
    return "Unknown"


def extract_year(publication):
    """
    Извлекает год публикации.
    
    Args:
        publication: XML элемент публикации
    
    Returns:
        int: год публикации или None
    """
    year_elem = publication.find("year")
    if year_elem is not None and year_elem.text:
        try:
            year = int(year_elem.text.strip())
            if 1900 <= year <= 2100:
                return year
        except ValueError:
            pass
    return None


def extract_title(publication):
    """
    Извлекает название публикации.
    
    Args:
        publication: XML элемент публикации
    
    Returns:
        str: название публикации или "Untitled"
    """
    title_elem = publication.find("title")
    if title_elem is not None and title_elem.text:
        return title_elem.text.strip()
    return "Untitled"


def parse_dblp_xml(xml_file, max_publications=None):
    """
    Потоковый парсинг XML файла DBLP для экономии памяти.
    
    Использует iterparse вместо parse, чтобы не загружать весь файл (несколько ГБ) 
    в память. Элементы обрабатываются по одному и сразу очищаются.
    
    Args:
        xml_file: путь к XML файлу
        max_publications: максимальное количество публикаций для обработки (None = все)
    
    Returns:
        tuple: (authors_list, publications, authorship_relations)
    """
    print("Начало потокового парсинга XML файла...")
    
    xml_file = os.path.abspath(xml_file)
    
    if not os.path.exists(xml_file):
        raise FileNotFoundError(f"XML файл не найден: {xml_file}")
    
    print(f"Парсинг файла: {xml_file}")
    if max_publications:
        print(f"Ограничение: максимум {max_publications} публикаций")
    
    author_dict = {}
    author_counter = 0
    publications = []
    authorship_relations = []
    
    publication_types = {"article", "inproceedings"}
    
    error_count = 0
    processed_count = 0
    
    print("Проверка формата файла...")
    with open(xml_file, 'rb') as f:
        first_bytes = f.read(100)
        is_html = first_bytes.startswith(b'<!DOCTYPE html') or first_bytes.startswith(b'<html')
    
    if is_html:
        print("Обнаружен HTML файл. Поиск XML данных внутри...")
        with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        dblp_start = content.find('<dblp>')
        if dblp_start == -1:
            dblp_start = content.find('<?xml')
            if dblp_start == -1:
                print("ОШИБКА: XML данные не найдены в файле.")
                print("Файл содержит только HTML. Нужен прямой XML файл DBLP.")
                print("Попробуйте скачать с: https://dblp.org/xml/dblp.xml.gz")
                return [], [], []
        
        print(f"Найдены XML данные на позиции {dblp_start}")
        xml_content = content[dblp_start:]
        
        temp_xml = os.path.abspath(xml_file + '.temp')
        with open(temp_xml, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        xml_file = temp_xml
    
    print("Использование потокового XML парсера (iterparse)...")
    parser = etree.XMLParser(
        recover=True, 
        huge_tree=True, 
        encoding='utf-8',
        no_network=True,
        resolve_entities=False
    )
    
    class NoExternalEntitiesResolver(etree.Resolver):
        def resolve(self, url, pubid, context):
            return self.resolve_empty(url)
    
    parser.resolvers.add(NoExternalEntitiesResolver())
    
    try:
        context = etree.iterparse(
            xml_file, 
            events=('end',), 
            tag=publication_types,
            huge_tree=True,
            recover=True,
            encoding='utf-8',
            no_network=True
        )
        
        for event, elem in context:
            try:
                if max_publications and processed_count >= max_publications:
                    print(f"Достигнут лимит в {max_publications} публикаций")
                    break
                
                pub_key = elem.get("key", "")
                if not pub_key:
                    elem.clear()
                    continue
                
                year = extract_year(elem)
                if year is None:
                    elem.clear()
                    continue
                
                authors = []
                for author_elem in elem.findall("author"):
                    author_name = normalize_author_name(author_elem.text)
                    if author_name:
                        authors.append(author_name)
                
                if not authors:
                    elem.clear()
                    continue
                
                pub_id = len(publications)
                publications.append({
                    "pub_id": pub_id,
                    "title": extract_title(elem),
                    "year": year,
                    "venue": extract_venue(elem),
                    "type": elem.tag,
                    "key": pub_key
                })
                
                for author_name in authors:
                    if author_name not in author_dict:
                        author_dict[author_name] = author_counter
                        author_counter += 1
                    
                    author_id = author_dict[author_name]
                    authorship_relations.append({
                        "pub_id": pub_id,
                        "author_id": author_id
                    })
                
                processed_count += 1
                
                if processed_count % 10000 == 0:
                    print(f"  Обработано: {processed_count} публикаций, авторов: {len(author_dict)}")
                
                elem.clear()
                while elem.getprevious() is not None:
                    try:
                        del elem.getparent()[0]
                    except (AttributeError, IndexError):
                        break
                    
            except Exception as e:
                error_count += 1
                if error_count <= 10:
                    print(f"Предупреждение: ошибка при обработке элемента: {e}")
                elif error_count == 11:
                    print("Дальнейшие ошибки будут подавлены...")
                try:
                    elem.clear()
                except Exception:
                    pass
                continue
        
        del context
        
    except Exception as e:
        print(f"Критическая ошибка при парсинге: {e}")
        raise
    finally:
        if xml_file.endswith('.temp'):
            try:
                os.remove(xml_file)
            except Exception:
                pass
    
    authors_list = [{"author_id": v, "author_name": k} for k, v in author_dict.items()]

    print(f"\nОбработано публикаций: {len(publications)}")
    print(f"Уникальных авторов: {len(authors_list)}")
    print(f"Связей автор-публикация: {len(authorship_relations)}")
    if error_count > 0:
        print(f"Пропущено элементов с ошибками: {error_count}")

    return authors_list, publications, authorship_relations


def build_coauthorship_graph(authorship_relations):
    """
    Строит граф соавторства из связей автор-публикация.
    
    Args:
        authorship_relations: список связей {pub_id, author_id}
    
    Returns:
        list: список ребер соавторства {author_id_1, author_id_2, weight}
    """
    print("Построение графа соавторства...")

    pub_to_authors = defaultdict(set)
    for rel in authorship_relations:
        pub_to_authors[rel["pub_id"]].add(rel["author_id"])

    coauthorship_edges = defaultdict(int)

    for pub_id, authors in pub_to_authors.items():
        authors_list = sorted(list(authors))
        for i in range(len(authors_list)):
            for j in range(i + 1, len(authors_list)):
                coauthorship_edges[(authors_list[i], authors_list[j])] += 1

    edges_list = [
        {"author_id_1": a1, "author_id_2": a2, "weight": w}
        for (a1, a2), w in coauthorship_edges.items()
    ]

    print(f"Ребер соавторства: {len(edges_list)}")
    return edges_list


def save_csv(filename, data, fieldnames):
    """
    Сохраняет данные в CSV файл.
    
    Args:
        filename: имя файла
        data: список словарей с данными
        fieldnames: список названий полей
    """
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Сохранено: {filepath} ({len(data)} записей)")


def main():
    """
    Основная функция: загружает, парсит XML и сохраняет результаты в CSV.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if os.path.exists(LOCAL_XML_FILE):
        file_size = os.path.getsize(LOCAL_XML_FILE)
        with open(LOCAL_XML_FILE, 'rb') as f:
            first_bytes = f.read(100)
            is_html = first_bytes.startswith(b'<!DOCTYPE html') or first_bytes.startswith(b'<html')
        
        if is_html or file_size < 1000000:
            print(f"Обнаружен некорректный файл (HTML или слишком мал: {file_size} байт).")
            print("Удаляем и загружаем правильный XML файл...")
            os.remove(LOCAL_XML_FILE)
    
    if not os.path.exists(LOCAL_XML_FILE):
        if os.path.exists(LOCAL_XML_GZ_FILE):
            print(f"Найден сжатый файл {LOCAL_XML_GZ_FILE}. Распаковка...")
            with gzip.open(LOCAL_XML_GZ_FILE, 'rb') as gz_file:
                with open(LOCAL_XML_FILE, 'wb') as xml_file:
                    xml_file.write(gz_file.read())
            print(f"Распаковка завершена: {LOCAL_XML_FILE}")
        else:
            print("\n" + "="*60)
            print("ИНСТРУКЦИЯ ПО ЗАГРУЗКЕ DBLP XML:")
            print("="*60)
            print("Скрипт попытается автоматически скачать файл.")
            print("Если автоматическая загрузка не работает, выполните:")
            print("1. Скачайте файл вручную:")
            print("   https://drops.dagstuhl.de/storage/artifacts/dblp/xml/2025/dblp-2025-12-01.xml.gz")
            print("   (или https://dblp.org/xml/dblp.xml.gz)")
            print("2. Распакуйте его (7-Zip, WinRAR или gunzip)")
            print("3. Поместите dblp.xml в текущую директорию")
            print("4. Запустите скрипт снова")
            print("="*60 + "\n")
            download_dblp_xml(DBLP_XML_URL, LOCAL_XML_FILE)

    print("\n" + "="*60)
    print("НАЧАЛО ПАРСИНГА (потоковый режим)")
    print("="*60)
    authors, publications, authorship = parse_dblp_xml(LOCAL_XML_FILE, max_publications=None)

    save_csv("authors.csv", authors, ["author_id", "author_name"])
    save_csv("publications.csv", publications, ["pub_id", "title", "year", "venue", "type", "key"])
    save_csv("authorship.csv", authorship, ["pub_id", "author_id"])

    coauthorship_edges = build_coauthorship_graph(authorship)
    save_csv("coauthorship_edges.csv", coauthorship_edges, ["author_id_1", "author_id_2", "weight"])

    print("\nЭтап 1 завершен успешно!")


if __name__ == "__main__":
    main()
