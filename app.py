import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import datetime
import json
import os
import io
import time

# 1. 페이지 설정 (반드시 가장 윗줄에 있어야 함)
st.set_page_config(page_title="발주현황 조회 시스템", layout="wide", page_icon="🏭")

# 2. 스타일 커스텀
st.markdown("""
<style>
    .block-container {padding-top: 3rem; padding-bottom: 2rem;}
    /* 버튼 너비 꽉 차게 */
    div.stButton > button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# 3. DB 연결 (안정성 강화)
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = None
        try:
            if "FIREBASE_KEY" in st.secrets:
                val = st.secrets["FIREBASE_KEY"]
                key_dict = json.loads(val, strict=False) if isinstance(val, str) else dict(val)
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(key_dict)
        except Exception as e:
            st.warning(f"⚠️ Secrets 설정 오류 감지: {e}")
        
        if cred is None:
            key_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
        
        if cred: firebase_admin.initialize_app(cred)
        
        if not firebase_admin._apps:
            st.error("❌ Firebase 연결 실패: 인증 키를 찾을 수 없습니다. Streamlit Secrets 설정을 확인해주세요.")
            st.stop()
    return firestore.client()

# 4. 데이터 로드 (캐싱 적용 + 예외 처리)
def load_data():
    try:
        db = get_db()
        docs = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
        data = [{"id": d.id, **d.to_dict()} for d in docs]
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ 데이터 불러오기 실패: {e}")
        return pd.DataFrame()

# 5. 화면 1: 로그인 페이지
def login_page():
    st.markdown("<br><br><br>", unsafe_allow_html=True) # 상단 여백
    login_container = st.empty()  # 화면 지움용 컨테이너
    with login_container.container():
        c1, c2, c3 = st.columns([1, 1, 1]) # 중앙 정렬
        with c2:
            st.title("🏭 발주현황 조회")
            with st.form("login_form"):
                st.write("접속 코드를 입력하세요.")
                code = st.text_input("Code", type="password", label_visibility="collapsed")
                submitted = st.form_submit_button("로그인", type="primary")
                
                if submitted:
                    if code == "1234":
                        st.session_state.auth_role = "client"
                        st.session_state.current_page = "신규 발주 등록"
                        login_container.empty()  # 로그인 성공 시 화면 즉시 비움
                        st.rerun()
                    elif code == "0000":
                        st.session_state.auth_role = "admin"
                        st.session_state.current_page = "발주 관리"
                        login_container.empty()  # 로그인 성공 시 화면 즉시 비움
                        st.rerun()
                    else:
                        st.error("코드가 올바르지 않습니다.")

# 6. 화면 2: 메인 어플리케이션
def main_app():
    # --- 사이드바 구성 ---
    st.sidebar.title("🏭 메뉴")
    
    # 네비게이션 버튼 함수
    def nav_btn(text, page_name, key=None):
        is_active = st.session_state.current_page == page_name
        if st.sidebar.button(text, type="primary" if is_active else "secondary", use_container_width=True, key=key):
            st.session_state.current_page = page_name
            st.rerun()

    # 메뉴 렌더링
    # 1. 거래처 기능 (공통)
    nav_btn("📝 신규 발주 등록", "신규 발주 등록", key="nav_new")
    nav_btn("🔍 진행상황 조회", "진행상황 조회", key="nav_search")

    # 2. 관리자 기능 (관리자만 보임)
    if st.session_state.auth_role == "admin":
        st.sidebar.divider()
        st.sidebar.subheader("관리자 기능")
        nav_btn("📋 발주 관리", "발주 관리", key="nav_manage")
        nav_btn("📤 엑셀 업로드", "엑셀 업로드", key="nav_upload")

    st.sidebar.divider()
    if st.sidebar.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.auth_role = None
        st.session_state.current_page = None
        st.rerun()

    # --- 메인 컨텐츠 렌더링 ---
    page = st.session_state.current_page
    db = get_db()

    if page == "신규 발주 등록":
        render_order_form(db)
    elif page == "진행상황 조회":
        render_status_view()
    elif page == "발주 관리":
        render_admin_manage(db)
    elif page == "엑셀 업로드":
        render_excel_upload(db)

# --- 각 페이지별 상세 로직 ---

def render_order_form(db):
    st.header("📝 신규 발주 등록")
    with st.form("new_order"):
        c1, c2 = st.columns(2)
        client = c1.text_input("업체명 (필수)")
        product = c2.text_input("품명 (필수)")
        
        c3, c4, c5 = st.columns(3)
        qty = c3.number_input("수량", step=10)
        spec = c4.text_input("규격")
        color = c5.text_input("색상")
        
        c6, c7, c8 = st.columns(3)
        yarn = c6.text_input("사종")
        weight = c7.text_input("중량")
        otype = c8.selectbox("구분", ["신규", "추가", "샘플"])
        
        c9, c10 = st.columns(2)
        mgr = c9.text_input("담당자")
        contact = c10.text_input("연락처")
        
        c11, c12 = st.columns(2)
        odate = c11.date_input("발주일", datetime.date.today())
        ddate = c12.date_input("납품요청일", datetime.date.today() + datetime.timedelta(days=7))
        
        st.markdown("---")
        c13, c14, c15 = st.columns(3)
        weaving = c13.text_input("제직 정보")
        dyeing = c14.text_input("염색 정보")
        site = c15.text_input("작업지")
        
        c16, c17 = st.columns(2)
        dest = c16.text_input("운송처")
        note = c17.text_input("비고")
        
        if st.form_submit_button("등록하기", type="primary"):
            if client and product:
                doc = {
                    "client_name": client, "product_name": product, "quantity": qty,
                    "unit": spec, "color": color, "yarn_type": yarn, "weight": weight,
                    "order_type": otype, "manager": mgr, "contact": contact,
                    "order_date": str(odate), "delivery_date": str(ddate),
                    "weaving": weaving, "dyeing": dyeing, "work_site": site,
                    "delivery_to": dest, "note": note,
                    "status": "발주접수", "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                db.collection("production_orders").add(doc)
                st.success("등록되었습니다.")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("업체명과 품명은 필수입니다.")

def render_status_view():
    st.header("🔍 진행상황 조회")
    search = st.text_input("검색", placeholder="업체명 또는 품명")
    df = load_data()
    
    if not df.empty:
        if search:
            mask = df['client_name'].astype(str).str.contains(search, na=False) | \
                   df['product_name'].astype(str).str.contains(search, na=False)
            df = df[mask]
        
        # 컬럼 정리
        cols = {
            'status': '상태', 'order_date': '발주일', 'client_name': '업체명', 
            'product_name': '품명', 'quantity': '수량', 'shipping_date': '출고일', 
            'shipping_method': '배송', 'note': '비고'
        }
        avail = [c for c in cols if c in df.columns]
        st.dataframe(df[avail].rename(columns=cols), hide_index=True, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

def render_admin_manage(db):
    st.header("📋 발주 관리")
    df = load_data()
    if df.empty:
        st.info("데이터가 없습니다.")
        return

    # 필터
    with st.expander("필터 옵션", expanded=True):
        c1, c2 = st.columns(2)
        stats = list(df['status'].unique()) if 'status' in df.columns else []
        sel_stats = c1.multiselect("상태 필터", [s for s in stats if isinstance(s, str)])
        txt = c2.text_input("검색어")
    
    mask = pd.Series(True, index=df.index)
    if sel_stats: mask &= df['status'].isin(sel_stats)
    if txt: mask &= (df['client_name'].astype(str).str.contains(txt) | df['product_name'].astype(str).str.contains(txt))
    
    df_show = df[mask].copy()
    
    # 에디터
    if 'selected' not in df_show.columns: df_show.insert(0, 'selected', False)
    
    cols_map = {
        'selected': '선택', 'status': '상태', 'client_name': '업체', 'product_name': '품명',
        'quantity': '수량', 'order_date': '발주일', 'weaving_date': '제직', 'dyeing_date': '염색',
        'sewing_date': '봉제', 'shipping_date': '출고'
    }
    disp_cols = [c for c in cols_map if c in df_show.columns]
    
    edited = st.data_editor(
        df_show[disp_cols + ['id']].rename(columns=cols_map),
        column_config={"선택": st.column_config.CheckboxColumn(width="small"), "id": None},
        disabled=[c for c in cols_map.values() if c != "선택"],
        hide_index=True, use_container_width=True
    )
    
    # 업데이트
    st.subheader("일괄 처리")
    with st.form("update"):
        c1, c2, c3 = st.columns(3)
        udate = c1.date_input("날짜", datetime.date.today())
        ustage = c2.selectbox("공정", ["제직공정", "염색공정", "봉제공정", "출고완료"])
        umethod = c3.selectbox("배송(출고시)", ["-", "택배", "화물", "직배송"])
        
        if st.form_submit_button("적용"):
            sel = edited[edited["선택"]]
            if not sel.empty:
                cnt = 0
                upd = {"status": ustage, "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                dstr = str(udate)
                if ustage == "제직공정": upd["weaving_date"] = dstr
                elif ustage == "염색공정": upd["dyeing_date"] = dstr
                elif ustage == "봉제공정": upd["sewing_date"] = dstr
                elif ustage == "출고완료":
                    upd["shipping_date"] = dstr
                    if umethod != "-": upd["shipping_method"] = umethod
                
                for _, r in sel.iterrows():
                    db.collection("production_orders").document(r['id']).update(upd)
                    cnt += 1
                st.success(f"{cnt}건 업데이트 완료")
                time.sleep(0.5)
                st.rerun()

    # 엑셀 다운로드 및 삭제
    st.divider()
    c_down, c_del = st.columns(2)
    with c_down:
        if st.button("선택 항목 엑셀 다운로드"):
            sel = edited[edited["선택"]]
            if not sel.empty:
                buf = io.BytesIO()
                sel.to_excel(buf, index=False)
                st.download_button("다운로드 파일 받기", buf.getvalue(), "selected.xlsx")
            else:
                st.warning("선택된 항목이 없습니다.")
    
    with c_del:
        with st.expander("데이터 전체 삭제"):
            if st.button("전체 삭제 실행", type="primary"):
                all_docs = db.collection("production_orders").stream()
                for d in all_docs: d.reference.delete()
                st.success("삭제 완료")
                st.rerun()

def render_excel_upload(db):
    st.header("📤 엑셀 업로드")
    up = st.file_uploader("파일", type=['xlsx'])
    if up:
        df = pd.read_excel(up)
        st.dataframe(df.head())
        if st.button("DB 저장"):
            for _, row in df.iterrows():
                doc = {str(k): str(v) for k, v in row.items()}
                doc['status'] = '발주접수'
                db.collection("production_orders").add(doc)
            st.success("완료")

# 7. 실행 진입점 (가장 중요: if-else 구조로 분리)
if 'auth_role' not in st.session_state:
    st.session_state.auth_role = None

if st.session_state.auth_role:
    main_app()
else:
    login_page()
