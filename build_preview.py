#!/usr/bin/env python3
"""
Omnichannel Group Blog - Local Static Preview Builder
Emulates Jekyll compilation so the site can be previewed locally and verified.
"""

import os
import re
import shutil
import html
import json
import yaml
import markdown
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(ROOT_DIR, '_site')

def parse_front_matter(content):
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                # The newline after the closing front-matter delimiter is not
                # page content.  Keeping it puts a blank line before XML
                # declarations, which makes feed.xml and sitemap.xml invalid.
                return fm, parts[2].lstrip('\r\n')
            except Exception as e:
                print(f"Error parsing front matter: {e}")
    return {}, content

def render_liquid_simple(text, context):
    """Render the Liquid subset used by this site for a faithful local preview."""
    context = context.copy()

    def var_repl(match):
        expr = match.group(1).strip()
        parts = [part.strip() for part in expr.split('|')]
        var_name = parts[0].strip()
        value = eval_var(var_name, context)
        for p in parts[1:]:
            if p.startswith('default:'):
                if value is None or value == '':
                    fallback = p.split(':', 1)[1].strip()
                    value = eval_var(fallback, context) if '.' in fallback else fallback.strip('"\'')
            elif p.startswith('date:'):
                fmt = p.split(':', 1)[1].strip().strip('"\'')
                try:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace(' +0530', '+05:30'))
                    value = value.strftime(fmt)
                except (AttributeError, ValueError):
                    value = ''
            elif p == 'date_to_xmlschema':
                try:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace(' +0530', '+05:30'))
                    value = value.isoformat()
                except (AttributeError, ValueError):
                    value = ''
            elif p == 'date_to_rfc822':
                try:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace(' +0530', '+05:30'))
                    value = value.strftime('%a, %d %b %Y %H:%M:%S %z')
                except (AttributeError, ValueError):
                    value = ''
            elif p == 'jsonify':
                return json.dumps(value or '')
            elif p in ('escape', 'xml_escape'):
                value = html.escape(str(value or ''), quote=True)
            elif p == 'downcase':
                value = str(value or '').lower()
            elif p.startswith('join:'):
                value = p.split(':', 1)[1].strip().strip('"\'').join(value or [])
            elif p == 'strip_html':
                value = re.sub(r'<[^>]+>', '', str(value or ''))
            elif p.startswith('truncate:'):
                limit = int(p.split(':', 1)[1].strip())
                value = str(value or '')[:limit]
            elif p == 'url_encode':
                from urllib.parse import quote
                value = quote(str(value or ''), safe='')

        return str(value or '')

    def render_variables(value):
        return re.sub(r'{{\s*([^}]+)\s*}}', var_repl, value)

    def condition_is_true(expression):
        expression = expression.strip()
        if '==' in expression:
            left, right = (part.strip() for part in expression.split('==', 1))
            return str(eval_var(left, context)) == right.strip('"\'')
        return bool(eval_var(expression, context))

    tag_pattern = re.compile(r'{%\s*(.*?)\s*%}', re.DOTALL)

    def render_section(start=0, stop_tags=()):
        output, cursor = [], start
        while True:
            tag_match = tag_pattern.search(text, cursor)
            if not tag_match:
                output.append(render_variables(text[cursor:]))
                return ''.join(output), len(text), None
            output.append(render_variables(text[cursor:tag_match.start()]))
            tag = tag_match.group(1).strip()
            command = tag.split(None, 1)[0] if tag else ''
            if command in stop_tags:
                return ''.join(output), tag_match.end(), command
            cursor = tag_match.end()

            if command == 'include':
                name = tag.split(None, 1)[1].strip()
                path = os.path.join(ROOT_DIR, '_includes', name)
                if os.path.exists(path):
                    output.append(render_liquid_simple(open(path, encoding='utf-8').read(), context))
            elif command == 'assign':
                assignment = tag.split(None, 1)[1]
                name, expression = (part.strip() for part in assignment.split('=', 1))
                context[name] = eval_var(expression, context)
            elif command == 'if':
                show_true = condition_is_true(tag.split(None, 1)[1])
                true_content, cursor, terminator = render_section(cursor, ('else', 'endif'))
                false_content = ''
                if terminator == 'else':
                    false_content, cursor, _ = render_section(cursor, ('endif',))
                output.append(true_content if show_true else false_content)
            elif command == 'for':
                match = re.match(r'for\s+(\w+)\s+in\s+([\w\.]+)(?:\s+limit:(\d+))?$', tag)
                body_start = cursor
                _, cursor, _ = render_section(cursor, ('endfor',))
                body = text[body_start:tag_pattern.search(text, body_start).start()] if False else None
                # Reconstruct the loop body from the original text.  Nested
                # blocks are already handled by render_section in each pass.
                end_tag_start = text.rfind('{%', body_start, cursor)
                body = text[body_start:end_tag_start]
                if match:
                    variable, collection_name, limit = match.groups()
                    values = eval_var(collection_name, context) or []
                    if limit:
                        values = values[:int(limit)]
                    for item in values:
                        child_context = context.copy()
                        child_context[variable] = item
                        output.append(render_liquid_simple(body, child_context))
            # End tags are consumed by the enclosing render_section.

    rendered, _, _ = render_section()
    return rendered

def eval_var(name, context):
    tokens = name.split('.')
    cur = context
    for t in tokens:
        if isinstance(cur, dict) and t in cur:
            cur = cur[t]
        elif t == 'first' and isinstance(cur, list):
            cur = cur[0] if cur else ''
        else:
            return ''
    return cur

def build():
    print("Building static site in _site/...")
    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(SITE_DIR, exist_ok=True)

    # 1. Load _config.yml
    config_path = os.path.join(ROOT_DIR, '_config.yml')
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    # Set site.time
    config['time'] = datetime.now().astimezone()

    # 2. Collect posts
    posts_dir = os.path.join(ROOT_DIR, '_posts')
    posts = []
    if os.path.exists(posts_dir):
        for fname in sorted(os.listdir(posts_dir), reverse=True):
            if fname.endswith(('.md', '.markdown', '.html')):
                fpath = os.path.join(posts_dir, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                fm, body = parse_front_matter(content)
                
                # Derive permalink: /category/YYYY/MM/DD/title/
                # or simplified permalink
                base_name = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', os.path.splitext(fname)[0])
                url = f"/posts/{base_name}.html"
                fm['url'] = url
                fm['date_str'] = "September 24, 2026"
                fm['filename'] = fname
                fm['raw_body'] = body
                posts.append(fm)

    # Match Jekyll's newest-first post ordering rather than filename order.
    posts.sort(key=lambda post: post.get('date', datetime.min), reverse=True)
    config['posts'] = posts
    site_ctx = {'site': config}

    # 3. Compile posts
    post_layout_path = os.path.join(ROOT_DIR, '_layouts', 'post.html')
    default_layout_path = os.path.join(ROOT_DIR, '_layouts', 'default.html')

    with open(post_layout_path, 'r', encoding='utf-8') as f:
        post_layout_raw = f.read()
    _, post_layout_body = parse_front_matter(post_layout_raw)

    with open(default_layout_path, 'r', encoding='utf-8') as f:
        default_layout_raw = f.read()
    _, default_layout_body = parse_front_matter(default_layout_raw)

    md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc'])

    for post in posts:
        post_ctx = {'site': config, 'page': post}
        
        # Convert markdown body to html
        html_body = md.reset().convert(post['raw_body'])
        # Python-Markdown decodes entities in raw HTML blocks. Re-escape bare
        # ampersands so the preview output remains valid HTML.
        html_body = re.sub(
            r'&(?!amp;|lt;|gt;|quot;|apos;|nbsp;|copy;|rarr;|larr;|darr;|le;|ge;|#(?:x[0-9A-Fa-f]+|[0-9]+);)',
            '&amp;', html_body,
        )
        
        # Render into post layout
        rendered_post = post_layout_body.replace('{{ content }}', html_body)
        rendered_post = render_liquid_simple(rendered_post, post_ctx)
        
        # Render into default layout
        final_html = default_layout_body.replace('{{ content }}', rendered_post)
        final_html = render_liquid_simple(final_html, post_ctx)

        # Output path: _site/posts/<base_name>.html
        out_file = os.path.join(SITE_DIR, post['url'].lstrip('/'))
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"Rendered post: {out_file}")

    # 4. Compile index.html
    index_path = os.path.join(ROOT_DIR, 'index.html')
    with open(index_path, 'r', encoding='utf-8') as f:
        idx_content = f.read()
    idx_fm, idx_body = parse_front_matter(idx_content)
    idx_ctx = {'site': config, 'page': idx_fm}

    rendered_idx = render_liquid_simple(idx_body, idx_ctx)
    final_index = default_layout_body.replace('{{ content }}', rendered_idx)
    final_index = render_liquid_simple(final_index, idx_ctx)

    with open(os.path.join(SITE_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(final_index)
    print("Rendered: _site/index.html")

    # 5. Compile about.html
    about_path = os.path.join(ROOT_DIR, 'about.html')
    if os.path.exists(about_path):
        with open(about_path, 'r', encoding='utf-8') as f:
            abt_content = f.read()
        abt_fm, abt_body = parse_front_matter(abt_content)
        abt_ctx = {'site': config, 'page': abt_fm}
        
        page_layout_path = os.path.join(ROOT_DIR, '_layouts', 'page.html')
        with open(page_layout_path, 'r', encoding='utf-8') as f:
            page_layout_raw = f.read()
        _, page_layout_body = parse_front_matter(page_layout_raw)

        rendered_abt = page_layout_body.replace('{{ content }}', abt_body)
        rendered_abt = render_liquid_simple(rendered_abt, abt_ctx)
        final_abt = default_layout_body.replace('{{ content }}', rendered_abt)
        final_abt = render_liquid_simple(final_abt, abt_ctx)

        about_out_dir = os.path.join(SITE_DIR, 'about')
        os.makedirs(about_out_dir, exist_ok=True)
        with open(os.path.join(about_out_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(final_abt)
        print("Rendered: _site/about/index.html")

    # 6. Compile 404.html
    err_path = os.path.join(ROOT_DIR, '404.html')
    if os.path.exists(err_path):
        with open(err_path, 'r', encoding='utf-8') as f:
            err_content = f.read()
        err_fm, err_body = parse_front_matter(err_content)
        err_ctx = {'site': config, 'page': err_fm}
        rendered_err = render_liquid_simple(err_body, err_ctx)
        final_err = default_layout_body.replace('{{ content }}', rendered_err)
        final_err = render_liquid_simple(final_err, err_ctx)
        with open(os.path.join(SITE_DIR, '404.html'), 'w', encoding='utf-8') as f:
            f.write(final_err)
        print("Rendered: _site/404.html")

    # 7. Render sitemap.xml & robots.txt & CNAME & feed.xml
    for static_file in ['robots.txt', 'CNAME']:
        src = os.path.join(ROOT_DIR, static_file)
        if os.path.exists(src):
            with open(src, 'r', encoding='utf-8') as f:
                content = f.read()
            rendered = render_liquid_simple(content, site_ctx)
            with open(os.path.join(SITE_DIR, static_file), 'w', encoding='utf-8') as f:
                f.write(rendered)

    # Render feed.xml (strip front matter)
    feed_src = os.path.join(ROOT_DIR, 'feed.xml')
    if os.path.exists(feed_src):
        with open(feed_src, 'r', encoding='utf-8') as f:
            feed_raw = f.read()
        _, feed_body = parse_front_matter(feed_raw)
        feed_out = render_liquid_simple(feed_body, site_ctx)
        with open(os.path.join(SITE_DIR, 'feed.xml'), 'w', encoding='utf-8') as f:
            f.write(feed_out)

    # Render sitemap.xml
    sitemap_src = os.path.join(ROOT_DIR, 'sitemap.xml')
    if os.path.exists(sitemap_src):
        with open(sitemap_src, 'r', encoding='utf-8') as f:
            sm_raw = f.read()
        _, sm_body = parse_front_matter(sm_raw)
        sm_out = render_liquid_simple(sm_body, site_ctx)
        with open(os.path.join(SITE_DIR, 'sitemap.xml'), 'w', encoding='utf-8') as f:
            f.write(sm_out)

    # 8. Copy assets/
    assets_src = os.path.join(ROOT_DIR, 'assets')
    assets_dst = os.path.join(SITE_DIR, 'assets')
    if os.path.exists(assets_src):
        shutil.copytree(assets_src, assets_dst)
        print("Copied assets to _site/assets")

    print("\n✅ Build complete! All files generated in _site/ successfully.")

if __name__ == '__main__':
    build()
