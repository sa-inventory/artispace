import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime
import pandas as pd
import json
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="아티스린넨 발주내역 진행상황", layout="wide", page_icon="🏭")

# 2. 데이터베이스 연결 (Firebase)
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = None
        # 스트림릿 클라우드 배포용 (Secrets)
        try:
            if "FIREBASE_KEY" in st.secrets:
                try:
                    key_dict = json.loads(st.secrets["FIREBASE_KEY"])
                    cred = credentials.Certificate(key_dict)
                except Exception as e:
                    st.error(f"Secrets 키 로드 실패: {e}")
        except Exception:
            # 로컬 환경에서 secrets.toml 파일이 없으면 무시하고 파일 인증으로 넘어감
            pass
        
        # 로컬 개발용 (파일)
        if cred is None:
            # 현재 파일(app.py)이 있는 폴더 경로를 기준으로 키 파일을 찾음
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            
            if os.path.exists(key_path):
                try:
                    cred = credentials.Certificate(key_path)
                except Exception as e:
                    st.error(f"❌ 키 파일 읽기 오류: {e}")
            else:
                st.warning(f"❌ 키 파일을 찾을 수 없습니다. 예상 경로: {key_path}")
        
        if cred:
            firebase_admin.initialize_app(cred)
            
    return firestore.client()

try:
    db = get_db()
except Exception as e:
    st.error(f"⚠️ 데이터베이스 연결 실패: {e}")
    if "default Firebase app does not exist" in str(e):
        st.warning("☁️ Streamlit Cloud의 [Secrets] 설정이 빠져있거나 잘못되었습니다. 앱 설정 메뉴에서 키 값을 확인해주세요.")
    st.stop()

# 공정 단계 정의
PROCESS_STAGES = ["발주접수", "제직공정", "염색공정", "봉제공정", "출고완료"]

# 메인 타이틀
st.title("🏭 Artispace 실시간 공정 현황")
st.markdown("---")

# 탭 구성: 조회용(거래처) / 입력용(관리자)
tab1, tab2 = st.tabs(["🔍 진행상황 조회 (거래처용)", "🛠️ 작업내역 입력 (관리자용)"])

# ==========================================
# 탭 1: 거래처 조회 화면
# ==========================================
with tab1:
    st.subheader("📦 발주 건별 진행상황")
    
    # 검색 기능
    col1, col2 = st.columns([3, 1])
    search_term = col1.text_input("발주처명 또는 품명을 입력하세요", placeholder="예: ABC물산")
    search_btn = col2.button("조회하기")

    # 데이터 가져오기
    orders_ref = db.collection("production_orders")
    query = orders_ref.order_by("order_date", direction=firestore.Query.DESCENDING)
    
    # 검색어가 있으면 필터링 (간단한 클라이언트 사이드 필터링)
    docs = query.stream()
    data_list = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        # 검색어가 없거나, 검색어가 발주처명/품명에 포함되면 추가
        if not search_term or (search_term in d.get('client_name', '')) or (search_term in d.get('product_name', '')):
            data_list.append(d)

    if data_list:
        # 보기 좋게 카드 형태로 출력
        for item in data_list:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                c1.write(f"**발주처**: {item['client_name']}")
                c2.write(f"**품명**: {item['product_name']}")
                c3.write(f"**수량**: {item['quantity']} {item.get('unit', 'yds')}")
                
                # 진행상태 시각화 (Progress Bar)
                current_stage = item['status']
                try:
                    progress_idx = PROCESS_STAGES.index(current_stage)
                    progress_val = (progress_idx + 1) / len(PROCESS_STAGES)
                except:
                    progress_val = 0
                
                c4.progress(progress_val, text=f"현재 상태: **{current_stage}**")
                
                # 상세 정보 (접기/펴기)
                with st.expander("상세 내역 보기"):
                    st.write(f"- 발주 일자: {item['order_date']}")
                    st.write(f"- 납품 예정처: {item.get('delivery_to', '-')}")
                    st.write(f"- 비고: {item.get('note', '-')}")
                    st.caption(f"최종 업데이트: {item.get('last_updated', '-')}")
    else:
        st.info("조회된 내역이 없습니다.")

# ==========================================
# 탭 2: 관리자 입력 화면
# ==========================================
with tab2:
    st.subheader("📝 신규 발주 등록")
    with st.form("new_order_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        client_name = c1.text_input("발주처명")
        product_name = c2.text_input("품명")
        
        c3, c4 = st.columns(2)
        quantity = c3.number_input("수량", min_value=1)
        unit = c4.selectbox("단위", ["yds", "meter", "kg", "pcs"])
        
        delivery_to = st.text_input("납품처 (선택사항)")
        note = st.text_area("비고 (특이사항)")
        
        submitted = st.form_submit_button("발주 등록")
        
        if submitted and client_name and product_name:
            new_data = {
                "client_name": client_name,
                "product_name": product_name,
                "quantity": quantity,
                "unit": unit,
                "delivery_to": delivery_to,
                "note": note,
                "status": "발주접수",  # 초기 상태
                "order_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            db.collection("production_orders").add(new_data)
            st.success("신규 발주가 등록되었습니다!")
            st.rerun()

    st.divider()
    st.subheader("🔄 공정 상태 업데이트")
    
    # 업데이트를 위한 목록 불러오기 (완료되지 않은 건 위주로)
    # 편의상 전체 목록을 불러와서 선택하는 방식으로 구현
    orders = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
    order_options = {doc.id: f"[{doc.to_dict().get('client_name')}] {doc.to_dict().get('product_name')} ({doc.to_dict().get('status')})" for doc in orders}
    
    if order_options:
        selected_order_id = st.selectbox("상태를 변경할 주문을 선택하세요", options=list(order_options.keys()), format_func=lambda x: order_options[x])
        
        if selected_order_id:
            # 현재 선택된 문서의 정보 가져오기
            doc_ref = db.collection("production_orders").document(selected_order_id)
            doc_snap = doc_ref.get()
            if doc_snap.exists:
                current_data = doc_snap.to_dict()
                st.info(f"현재 상태: **{current_data['status']}**")
                
                new_status = st.selectbox("변경할 상태 선택", PROCESS_STAGES, index=PROCESS_STAGES.index(current_data['status']) if current_data['status'] in PROCESS_STAGES else 0)
                
                if st.button("상태 변경 저장"):
                    doc_ref.update({
                        "status": new_status,
                        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    st.success(f"'{new_status}' 상태로 변경되었습니다.")
                    st.rerun()
    else:
        st.write("업데이트할 주문 내역이 없습니다.")