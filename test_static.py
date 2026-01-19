from app import app

def fetch(path):
    with app.test_client() as c:
        r = c.get(path)
        print(f"GET {path} -> {r.status_code}  Content-Type: {r.headers.get('Content-Type')}")
        data = r.data.decode('utf-8', errors='replace')
        print(data[:800].replace('\n','\\n'))
        print('---')

if __name__ == '__main__':
    print('app.root_path:', app.root_path)
    print('app.static_folder:', app.static_folder)
    import os
    print('static abs path:', os.path.abspath(app.static_folder))
    fetch('/')
    fetch('/static/css/style.css')
    fetch('/static/style.css')
    fetch('/static/js/main.js')
    # Check raw bytes on disk for encoding issues
    for path in ['static/css/style.css', 'static/js/main.js']:
        try:
            with open(path, 'rb') as f:
                b = f.read()
                print(path, 'raw bytes (first16):', b[:16])
                print(path, 'hex:', b[:16].hex())
                try:
                    print(path, 'utf-8:', b.decode('utf-8')[:800].replace('\n','\\n'))
                except Exception:
                    print(path, 'utf-8: <decode error>')
                try:
                    print(path, 'utf-16-le:', b.decode('utf-16le')[:800].replace('\n','\\n'))
                except Exception:
                    print(path, 'utf-16-le: <decode error>')
                print(path, 'size:', len(b))
        except Exception as e:
            print('error reading', path, e)
