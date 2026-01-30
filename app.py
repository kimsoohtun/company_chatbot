import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. 설정 및 API 연결 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    api_key = ""
    gsheet_url = ""

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 구글 시트 로드 함수 (오류 방지 강화) ---
def load_gsheet_data(url):
    if not url: return ""
    try:
        csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in url else url
        # on_bad_lines='skip'을 추가하여 형식이 깨진 행은 무시하고 읽습니다.
        df = pd.read_csv(csv_url, on_bad_lines='skip')
        return df.to_string(index=False)
    except Exception as e:
        st.error(f"구글 시트를 읽는 데 실패했습니다: {e}")
        return ""

# --- 3. UI 및 데이터 로드 ---
st.title("🤖 사내 규정 안내 챗봇")
knowledge_base = load_gsheet_data(gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # 404 오류 해결을 위해 가장 기본적인 모델명을 사용합니다.
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 컨텍스트 제한 (429 예방)
            safe_context = knowledge_base[:30000] 
            
            full_query = f"지식 베이스:\n{safe_context}\n\n질문: {prompt}"
            
            response = model.generate_content(full_query)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            # 상세한 에러 내용을 출력하여 원인을 파악합니다.
            st.error(f"⚠️ 상세 오류: {e}")
