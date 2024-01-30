import re
from flask import Flask, render_template, request, send_file
from flask_cors import CORS, cross_origin
import pandas as pd
import unicodedata
import os
# from dotenv import load_dotenv

app = Flask(__name__, template_folder='./templates', static_folder='./static')
origins = [
    "https://normalize-dakuten-jzlg.vercel.app/",
    "http://localhost:5173",
]
CORS(app, origins=origins)

# セキュリティヘッダーの設定
@app.after_request
def set_security_headers(response):
    # XSS対策: Content Security Policy (CSP)
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    # ブラウザによるMIMEタイプスニッフィングの無効化
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # フレーム内でのページ表示を許可しない
    response.headers['X-Frame-Options'] = 'DENY'
    # XSSフィルタを有効化
    response.headers['X-XSS-Protection'] = '1; mode=block'

    return response

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def normalize_data(file):
    # str -> bytes
    bytes_text = file.encode()
    # 濁点Unicode結合文字置換
    bytes_text = re.sub(b"\xe3\x82\x9b", b'\xe3\x82\x99', bytes_text)
    bytes_text = re.sub(b"\xef\xbe\x9e", b'\xe3\x82\x99', bytes_text)
    # 半濁点Unicode結合文字置換
    bytes_text = re.sub(b"\xe3\x82\x9c", b'\xe3\x82\x9a', bytes_text)
    bytes_text = re.sub(b"\xef\xbe\x9f", b'\xe3\x82\x9a', bytes_text)
    # byte_text -> str
    file = bytes_text.decode()
    # 正規化
    file = unicodedata.normalize("NFC", file)
    return file

@app.route('/')
def Home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def handle_upload():
    try:
        file = request.files['file']
        if file:
            # アップロードされたファイルを保存
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)

            # 正規化されたファイル名を生成
            re_prefixed_filename = f"re.{file.filename}"

            # ファイルの内容をPandasデータフレームに変換
            if re_prefixed_filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(filename, engine='openpyxl', index_col=None, header=None)
            elif re_prefixed_filename.endswith('.csv'):
                try:
                    # UTF-8-SIGで読み込みを試みる
                    df = pd.read_csv(filename, index_col=None, header=None, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    # UTF-8-SIGで読み込めない場合はshift-jisで再試行
                    df = pd.read_csv(filename, index_col=None, header=None, encoding='shift-jis')

            # ファイルの内容をunicodedataで正規化
            df_normalized = df.applymap(lambda x: normalize_data(x) if pd.notna(x) else x)

            # ファイルを正規化されたファイル名で保存
            re_prefixed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], re_prefixed_filename)
            if re_prefixed_filename.endswith(('.xls', '.xlsx')):
                df_normalized.to_excel(re_prefixed_filepath, index=False, header=False)
            elif re_prefixed_filename.endswith('.csv'):
                df_normalized.to_csv(re_prefixed_filepath, index=False, header=False)

            # os.remove(filename)
            # 正規化されたファイルを直接レスポンスの本文に含めて返す
            return send_file(re_prefixed_filepath, as_attachment=True)
    except Exception as e:
        return str(e), 400

if __name__ == '__main__':
    app.run()

