#!/usr/bin/env python3
"""
Omnichannel Group Blog - Local Static Preview Builder
Emulates Jekyll compilation so the site can be previewed locally and verified.
"""

import os
import re
import shutil
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
                return fm, parts[2]
            except Exception as e:
                print(f"Error parsing front matter: {e}")
    return {}, content

def render_liquid_simple(text, context):
    """Simple Liquid replacement for variables and includes"""
    site = context.get('site', {})
    page = context.get('page', {})
    
    # Handle includes: {% include filename.html %}
    include_pattern = re.compile(r'{%\s*include\s+([\w\.\-]+)\s*%}')
    def replace_include(match):
        inc_name = match.group(1)
        inc_path = os.path.join(ROOT_DIR, '_includes', inc_name)
        if os.path.exists(inc_path):
            with open(inc_path, 'r', encoding='utf-8') as f:
                return render_liquid_simple(f.read(), context)
        return ''
    text = include_pattern.sub(replace_include, text)

    # Handle simple for loops for posts: {% for post in site.posts %} ... {% endfor %}
    for_post_pattern = re.compile(r'{%\s*for\s+post\s+in\s+site\.posts(?:\s+limit:(\d+))?\s*%}(.*?){%\s*endfor\s*%}', re.DOTALL)
    def replace_posts_loop(match):
        limit = int(match.group(1)) if match.group(1) else None
        template = match.group(2)
        out = []
        posts = site.get('posts', [])
        if limit:
            posts = posts[:limit]
        for p in posts:
            p_ctx = {'site': site, 'page': page, 'post': p}
            p_text = template
            # replace {{ post.xyz }}
            for k, v in p.items():
                if isinstance(v, (str, int, float)):
                    p_text = re.sub(r'{{\s*post\.' + k + r'(?:\s*\|[^}]*)?\s*}}', str(v), p_text)
            # handle post.tags
            p_text = re.sub(r'{%\s*for\s+tag\s+in\s+post\.tags\s*%}[\s\S]*?{%\s*endfor\s*%}', '', p_text)
            out.append(p_text)
        return ''.join(out)
    text = for_post_pattern.sub(replace_posts_loop, text)

    # Replace simple variables {{ site.xyz }} and {{ page.xyz }}
    def var_repl(match):
        expr = match.group(1).strip()
        parts = expr.split('|')
        var_name = parts[0].strip()
        default_val = ''
        for p in parts[1:]:
            p = p.strip()
            if p.startswith('default:'):
                default_val = p.split(':', 1)[1].strip().strip('"\'')
            elif p.startswith('date:'):
                fmt = p.split(':', 1)[1].strip().strip('"\'')
                # If date formatting
                if var_name == 'site.time':
                    return datetime.now().strftime('%Y')
                elif var_name in ('page.date', 'post.date'):
                    try:
                        d = page.get('date') or datetime.now()
                        if isinstance(d, str):
                            d = datetime.fromisoformat(d.replace(' +0530', ''))
                        return d.strftime('%B %d, %Y')
                    except Exception:
                        return "September 24, 2026"
            elif p == 'date_to_xmlschema':
                return datetime.now().isoformat()
            elif p == 'date_to_rfc822':
                return datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
            elif p == 'jsonify':
                import json
                val = eval_var(var_name, context) or default_val
                return json.dumps(val)

        val = eval_var(var_name, context)
        if val is None or val == '':
            return default_val
        return str(val)

    text = re.sub(r'{{\s*([^}]+)\s*}}', var_repl, text)

    # Clean up unhandled liquid tags gracefully
    text = re.sub(r'{%[^{}%]*%}', '', text)

    return text

def eval_var(name, context):
    tokens = name.split('.')
    cur = context
    for t in tokens:
        if isinstance(cur, dict) and t in cur:
            cur = cur[t]
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
    config['time'] = datetime.now()

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

    # First featured post helper in template
    if posts:
        feat = posts[0]
        idx_body = idx_body.replace('{{ featured_post.url }}', feat['url'])
        idx_body = idx_body.replace('{{ featured_post.title }}', feat.get('title', ''))
        idx_body = idx_body.replace('{{ featured_post.subtitle | default: featured_post.description }}', feat.get('subtitle', ''))
        idx_body = idx_body.replace('{{ featured_post.category | default: "AI Engineering" }}', feat.get('category', 'AI Engineering'))
        idx_body = idx_body.replace('{{ featured_post.read_time | default: "15 min read" }}', feat.get('read_time', '15 min read'))
        idx_body = idx_body.replace('{{ featured_post.image | default: \'/assets/images/spec-driven-engineering-banner.jpg\' }}', feat.get('image', '/assets/images/spec-driven-engineering-banner.jpg'))
        idx_body = idx_body.replace('{{ featured_post.date | date: "%b %d, %Y" }}', 'Sep 24, 2026')
        idx_body = idx_body.replace('{{ featured_post.author | default: site.author.name }}', feat.get('author', config.get('author', {}).get('name', '')))

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
