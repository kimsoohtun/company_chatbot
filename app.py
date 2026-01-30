import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai
import os

# --- 1. 관리자 설정 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    api_key = "" 
    gsheet_url = "" 

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 텍스트 추출 로직 ---
def extract_text_from_folder(folder_path, g_url):
    text_data = ""
    sources = []
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            content = ""
            try:
                if filename.endswith('.pdf'):
                    with pdfplumber.open(file_path) as pdf:
                        content = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                elif filename.endswith('.docx'):
                    content = "\n".join([p.text for p in Document(file_path).paragraphs])
                elif filename.endswith('.xlsx'):
                    content = pd.read_excel(file_path).to_string()
                
                if content:
                    text_data += f"\n\n[출처: {filename}]\n{content}"
                    sources.append(filename)
            except Exception as e:
                st.error(f"파일 {filename} 읽기 실패: {e}")

    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
    return text_data, sources

# --- 3. UI 및 지식 로드 ---
st.set_page_config(page_title="사내 규정 챗봇", layout="centered")
st.title("🤖 사내 규정 안내 챗봇")
st.markdown("---")

# 지식 구축 (data 폴더 읽기)
knowledge_base, source_list = extract_text_from_folder("data", gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("궁금한 규정을 물어보세요."):
    if not api_key:
        st.error("관리자 설정(API Key)이 필요합니다.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # 404 에러 방지를 위한 가장 확실한 모델 호출 방식
                # 1.5-flash가 안 될 경우를 대비해 모델명을 명확히 지정합니다.
                model = genai.GenerativeModel('gemini-1.0-pro')
                
                # 429 에러 방지 (입력 데이터 제한)
                safe_context = knowledge_base[:70000]
                
                full_query = f"""너는 사내 규정 전문가야. 아래 지식 베이스를 바탕으로 답변해줘.
                답변 끝에 '참고 문서: [문서명]'을 꼭 적어줘. 
                모르는 내용은 반드시 '인사팀에 문의하세요'라고 답변해.
                
                [지식 베이스(일부)]
                {safe_context}
                
                질문: {prompt}"""
                
                response = model.generate_content(full_query)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                # 404 에러가 계속될 경우 구버전 모델명인 'gemini-pro'로 자동 전환 시도
                if "404" in str(e):
                    try:
                        model = genai.GenerativeModel('gemini-pro')
                        response = model.generate_content(full_query)
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e2:
                        st.error(f"모델을 찾을 수 없습니다: {e2}")
                elif "429" in str(e):
                    st.error("⚠️ 너무 많은 요청이 들어왔습니다. 1분 뒤에 다시 시도해 주세요.")
                else:
                    st.error(f"오류가 발생했습니다: {e}")

