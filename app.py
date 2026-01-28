import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai
import os

# --- 1. 관리자 설정 (Secrets 우선, 없으면 기본값) ---
try:
    # 배포 환경 (Streamlit Secrets 사용)
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    # 로컬 테스트 환경
    api_key = "" # 실제 키를 여기 적거나 빈칸으로 두세요
    gsheet_url = "" 

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 텍스트 추출 로직 (파일 경로 대응) ---
def extract_text_from_folder(folder_path, g_url):
    text_data = ""
    sources = []
    
    # 2-1. 지정된 폴더(data) 내의 파일들을 자동으로 읽기
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

    # 2-2. 구글 시트 처리
    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
        
    return text_data, sources

# --- 3. UI 구성 (직원용 깔끔한 화면) ---
st.set_page_config(page_title="사내 규정 챗봇", layout="centered")
st.title("🤖 사내 규정 안내 챗봇")
st.markdown("---")

# 지식 구축 (data 폴더를 자동으로 읽음)
# GitHub 저장소에 'data' 폴더를 만들고 문서를 넣어두세요!
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
                model = genai.GenerativeModel('gemini-2.5-flash')
                full_query = f"""너는 사내 규정 전문가야. 아래 지식 베이스를 바탕으로 답변해줘.
                답변 끝에 '참고 문서: [문서명]'을 꼭 적어줘. 
                모르는 내용은 반드시 '인사팀에 문의하세요'라고 답변해.
                
                [지식 베이스]
                {knowledge_base}
                
                질문: {prompt}"""
                
                response = model.generate_content(full_query)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

