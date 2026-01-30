import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. 설정 및 API 연결 ---
# Streamlit Secrets에서 정보를 가져옵니다.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    api_key = ""
    gsheet_url = ""

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 구글 시트 데이터 로드 함수 ---
def load_gsheet_data(url):
    if not url:
        return ""
    try:
        # 구글 시트 URL을 CSV 내보내기 형식으로 변환
        csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in url else url
        if "export?format=csv" not in csv_url:
            csv_url = csv_url.rstrip('/') + '/export?format=csv'
            
        df = pd.read_csv(csv_url)
        # 시트의 전체 내용을 텍스트 하나로 합칩니다.
        return df.to_string(index=False)
    except Exception as e:
        st.error(f"구글 시트를 읽는 데 실패했습니다: {e}")
        return ""

# --- 3. UI 구성 ---
st.set_page_config(page_title="사내 규정 챗봇 (시트 전용)", layout="centered")
st.title("🤖 구글 시트 기반 규정 안내 챗봇")
st.info("현재 구글 시트에 등록된 데이터만을 바탕으로 답변합니다.")

# 지식 베이스 구축 (구글 시트만 읽음)
with st.spinner("구글 시트 데이터를 가져오는 중..."):
    knowledge_base = load_gsheet_data(gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 기록 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("시트 내용에 대해 물어보세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # AI Studio 키에 가장 최적화된 모델 호출
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 지식 베이스가 너무 길 경우를 대비해 자르기 (429 예방)
            safe_context = knowledge_base[:50000] 
            
            full_query = f"""너는 구글 시트에 기록된 사내 규정을 안내하는 전문가야. 
아래 [지식 베이스]의 내용만 참고해서 답변해줘. 시트에 없는 내용은 '인사팀에 문의하세요'라고 해.

[지식 베이스]
{safe_context}

질문: {prompt}"""
            
            response = model.generate_content(full_query)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            if "404" in str(e):
                st.error("⚠️ 모델을 찾을 수 없습니다. API 키 설정을 다시 확인해주세요.")
            elif "429" in str(e):
                st.error("⚠️ 너무 많은 요청이 들어왔습니다. 잠시 후 다시 시도해주세요.")
            else:
                st.error(f"오류가 발생했습니다: {e}")
