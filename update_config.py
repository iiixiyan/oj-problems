"""
OJ题库增量更新工具
扫描OJ_title目录，提取新增HTML文件的题目描述，追加到已有的config.json和config.js中。

用法:
  python update_config.py            # 增量更新（仅处理新增文件）
  python update_config.py --rebuild  # 全量重建（重新提取所有文件描述）
  python update_config.py --dir PATH # 指定题目目录（默认OJ_title）
"""
import os, json, re, sys
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self.skip = False
        self.skip_tags = {'script', 'style', 'code', 'pre', 'nav', 'footer', 'header'}

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip = True

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            t = data.strip()
            if t:
                self.texts.append(t)

    def handle_entityref(self, name):
        entities = {
            'lt': '<', 'gt': '>', 'amp': '&', 'quot': '"', 'nbsp': ' ', 'apos': "'",
            'xff0c': ',', 'xff1a': ':', 'xff1b': ';', 'xff08': '(', 'xff09': ')',
            'xff0d': '-', 'xfe2c': '~', 'x0d': '\r',
        }
        if not self.skip:
            self.texts.append(entities.get(name, ''))

    def handle_charref(self, name):
        if not self.skip:
            try:
                if name.startswith('x') or name.startswith('X'):
                    c = chr(int(name[1:], 16))
                else:
                    c = chr(int(name))
                self.texts.append(c)
            except:
                pass

    def get_text(self):
        return '\n'.join(self.texts)


def read_html(filepath):
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ''


def extract_question_text(filepath):
    try:
        html = read_html(filepath)
        if not html:
            return ''

        content_match = re.search(r'id="article_content"[^>]*>(.*?)</div>\s*</div>\s*<h4', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'id="content_views"[^>]*>(.*?)</div>\s*</div>\s*<h4', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'id="content_views"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)

        source = content_match.group(1) if content_match else html

        code_start = re.search(r'<(?:pre|code)\b', source)
        if code_start:
            source = source[:code_start.start()]

        extractor = TextExtractor()
        extractor.feed(source)
        text = extractor.get_text().strip()
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text[:3000] if len(text) > 50 else ''
    except Exception as e:
        print(f'  [WARN] 提取失败: {filepath} - {e}')
        return ''


def parse_filename(f):
    score = 100
    m = re.search(r'(\d+)分', f)
    if m:
        score = int(m.group(1))

    tags = []
    vm = re.search(r'\(([ABCDE]卷)[,，]', f)
    if vm:
        tags.append(vm.group(1))
    if '2025B' in f:
        tags.append('2025B')

    title = f
    for pat in [
        r'^\([^)]*\)\s*[-–]?\s*',
        r'（Java\s*&\s*JS\s*&\s*Python[^）]*）',
        r'（python、java、c\+\+、js、c）',
        r'（Java\s*&\s*Python[^）]*）',
        r'\(Java\s*&\s*JS\s*&\s*Python[^)]*\)',
        r'\.html$',
        r'[-–]\s*$',
        r'^\s*[-–]\s*',
    ]:
        title = re.sub(pat, '', title)
    title = title.strip()
    if len(title) < 2:
        title = f.replace('.html', '').strip()

    return title, score, tags


def load_existing_config(config_path):
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            return data
        except:
            pass
    return {'questions': []}


def save_config(config, config_path, js_path):
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    js_content = 'window.questionsConfig = ' + json.dumps(config, ensure_ascii=False, indent=2) + ';'
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)


def update(dir_path='OJ_title', rebuild=False):
    config_path = 'config.json'
    js_path = 'config.js'

    config = load_existing_config(config_path) if not rebuild else {'questions': []}
    existing_files = {q['file'] for q in config['questions']}

    all_files = sorted(os.listdir(dir_path))
    new_count = 0
    update_count = 0

    print(f'扫描目录: {dir_path}/')
    print(f'已有题目: {len(config["questions"])} 道')
    print(f'目录文件: {len(all_files)} 个')

    for f in all_files:
        file_key = f'{dir_path}/{f}'
        filepath = os.path.join(dir_path, f)

        if not rebuild and file_key in existing_files:
            # 增量模式：已存在的跳过（除非需要更新desc）
            existing_q = next((q for q in config['questions'] if q['file'] == file_key), None)
            if existing_q and existing_q.get('desc', '').strip():
                continue
            # desc为空，重新提取
            desc = extract_question_text(filepath)
            if desc:
                existing_q['desc'] = desc
                update_count += 1
            continue

        title, score, tags = parse_filename(f)
        desc = extract_question_text(filepath)

        next_id = 'q' + str(len(config['questions']) + 1).zfill(3)
        config['questions'].append({
            'id': next_id,
            'title': title,
            'score': score,
            'file': file_key,
            'tags': tags,
            'desc': desc,
        })
        new_count += 1

    save_config(config, config_path, js_path)

    total = len(config['questions'])
    has_desc = sum(1 for q in config['questions'] if q.get('desc', '').strip())
    print(f'\n更新完成:')
    print(f'  新增: {new_count} 道')
    print(f'  补充描述: {update_count} 道')
    print(f'  总计: {total} 道 (含描述: {has_desc})')
    print(f'  已写入: {config_path}, {js_path}')


if __name__ == '__main__':
    rebuild = '--rebuild' in sys.argv
    dir_path = 'OJ_title'
    for i, arg in enumerate(sys.argv):
        if arg == '--dir' and i + 1 < len(sys.argv):
            dir_path = sys.argv[i + 1]
    update(dir_path, rebuild)
