import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai

# --- 1. 설정 및 UI ---
st.set_page_config(page_title="사내 규정 챗봇", layout="wide")
st.title("🤖 2026 통합 규정 안내 챗봇")

with st.sidebar:
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    if api_key:
        genai.configure(api_key=api_key)
    
    st.divider()
    st.subheader("파일 업로드")
    uploaded_files = st.file_uploader("문서 선택 (PDF, XLSX, DOCX)", 
                                    accept_multiple_files=True, 
                                    type=['pdf', 'xlsx', 'docx'])
    gsheet_url = st.text_input("구글 시트 URL")

# --- 2. 텍스트 추출 로직 ---
def extract_text(files, g_url):
    text_data = ""
    sources = []
    for f in files:
        content = ""
        if f.name.endswith('.pdf'):
            with pdfplumber.open(f) as pdf:
                content = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif f.name.endswith('.docx'):
            content = "\n".join([p.text for p in Document(f).paragraphs])
        elif f.name.endswith('.xlsx'):
            content = pd.read_excel(f).to_string()
        text_data += f"\n\n[출처: {f.name}]\n{content}"
        sources.append(f.name)
    
    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
    return text_data, sources

# --- 3. 채팅 엔진 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 지식 구축
knowledge_base, source_list = extract_text(uploaded_files, gsheet_url)

# 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 질문 처리
if prompt := st.chat_input("질문을 입력하세요"):
    if not api_key:
        st.error("API 키가 필요합니다.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # 리스트에 있는 모델 중 하나를 선택 (Gemini 2.5 Flash 권장)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # 변수명을 full_query로 통일하여 에러 방지
                full_query = f"""너는 사내 규정 전문가야. 다음 지식을 바탕으로 답변해줘.
                답변 끝에 참고한 문서명을 적어줘. 모르면 '인사팀 문의'라고 해.
                
                [지식 베이스]
                {knowledge_base}
                
                질문: {prompt}"""
                
                response = model.generate_content(full_query)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"오류 발생: {e}")