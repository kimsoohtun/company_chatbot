import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai
import os

# --- 1. 관리자 설정 (Secrets 우선) ---
try:
    # 배포 환경 (Streamlit Secrets 사용)
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    # 로컬 테스트 환경용 (비워두고 secrets.toml 사용 권장)
    api_key = "" 
    gsheet_url = "" 

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 텍스트 추출 로직 (파일 경로 대응) ---
def extract_text_from_folder(folder_path, g_url):
    text_data = ""
    sources = []
    
    # 지정된 폴더(data) 내의 파일들을 자동으로 읽기
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

    # 구글 시트 처리
    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
        
    return text_data, sources

# --- 3. UI 구성 (직원용 깔끔한 화면) ---
# 사이드바를 기본적으로 닫아두고 메인 화면에 집중하게 합니다.
st.set_page_config(page_title="사내 규정 챗봇", layout="centered", initial_sidebar_state="collapsed")
st.title("🤖 2026 통합 규정 안내 챗봇")
st.info("안녕하세요! 사내 규정에 대해 무엇이든 물어보세요.")
st.markdown("---")

# 지식 구축 (data 폴더를 자동으로 읽음)
# GitHub 저장소에 'data' 폴더를 만들고 문서를 넣어두어야 합니다.
knowledge_base, source_list = extract_text_from_folder("data", gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 내용 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("궁금한 규정을 물어보세요."):
    # ... (생략: 메시지 추가 로직) ...

with st.chat_message("assistant"):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash') # 최신 안정 버전 사용 권장
        
        # [핵심] 전체 지식 중 앞부분 약 5~7만 자만 잘라서 보냅니다.
        # 한글 기준 약 70,000자는 무료 한도 내에서 매우 안전하게 작동합니다.
        safe_context = knowledge_base[:70000] 
        
        full_query = f"""너는 사내 규정 전문가야. 아래 제공된 [지식 베이스]를 바탕으로 답변해줘.
        답변 끝에 '참고 문서: [문서명]'을 꼭 적어줘. 
        모르는 내용은 반드시 '인사팀에 문의하세요'라고 답변해.
        
        [지식 베이스(일부)]
        {safe_context}
        
        질문: {prompt}"""
        
        response = model.generate_content(full_query)
            
        except Exception as e:
            # 429 에러가 발생했을 때 사용자에게 친절하게 안내
            if "429" in str(e):
                st.error("⚠️ 한꺼번에 너무 많은 정보를 처리하고 있습니다. 약 1분 뒤에 다시 질문해 주세요.")
            else:
                st.error(f"오류가 발생했습니다: {e}")



