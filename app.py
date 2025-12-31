import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import datetime
import json
import os
import io

# 1. 페이지 설정 (반드시 가장 윗줄에 있어야 함)
st.set_page_config(page_title="발주현황 조회 시스템", layout="wide", page_icon="🏭")

# 2. 스타일 커스텀 (화면 여백 줄이기)
st.markdown("""
<style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
</style>
""", unsafe_allow_html=True)

# 3. DB 연결 (안정성 강화 버전)
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = None
        try:
            if "FIREBASE_KEY" in st.secrets:
                val = st.secrets["FIREBASE_KEY"]
                # 문자열이면 JSON 파싱, 딕셔너리면 바로 사용
                key_dict = json.loads(val, strict=False) if isinstance(val, str) else dict(val)
                # 줄바꿈 문자 처리
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(key_dict)
        except: pass
        
        if cred is None:
            # 로컬 파일 확인
            key_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
        
        if cred: firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = get_db()
except Exception as e:
    st.error(f"DB 연결 오류: {e}")
    st.stop()

# 4. 공통 함수: 데이터 로드
def load_data():
    try:
        docs = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
        data = [{"id": d.id, **d.to_dict()} for d in docs]
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# 5. 로그인 및 세션 관리
if 'auth_role' not in st.session_state:
    st.session_state.auth_role = None

if st.session_state.auth_role is None:
    st.title("🏭 발주현황 조회 시스템")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            st.subheader("로그인")
            code = st.text_input("접속 코드", type="password")
            if st.form_submit_button("접속하기"):
                if code == "1234":
                    st.session_state.auth_role = "client"
                    st.rerun()
                elif code == "0000": # 관리자 코드
                    st.session_state.auth_role = "admin"
                    st.rerun()
                else:
                    st.error("접속 코드가 올바르지 않습니다.")
    st.stop()

# 6. 사이드바 메뉴 (권한별 노출)
st.sidebar.title("🏭 Artispace")

if st.session_state.auth_role == "admin":
    menu = st.sidebar.radio("메뉴 선택", ["거래처용 (조회/등록)", "관리자용 (공정 관리)"])
else:
    menu = "거래처용 (조회/등록)"

st.sidebar.divider()
if st.sidebar.button("로그아웃"):
    st.session_state.auth_role = None
    st.rerun()

# ==========================================
# VIEW 1: 거래처용
# ==========================================
if menu == "거래처용 (조회/등록)":
    st.title("📦 거래처 발주 시스템")
    
    tab_view, tab_reg = st.tabs(["🔍 진행상황 조회", "📝 신규 발주 등록"])
    
    # --- 조회 탭 ---
    with tab_view:
        search = st.text_input("검색 (업체명, 품명)", placeholder="검색어 입력...")
        
        df = load_data()
        if not df.empty:
            # 필터링
            if search:
                mask = df['client_name'].astype(str).str.contains(search, na=False) | \
                       df['product_name'].astype(str).str.contains(search, na=False)
                df = df[mask]
            
            # 보여줄 컬럼 정의
            cols_client = {
                'status': '진행상태', 'order_date': '발주일', 'client_name': '업체명', 
                'product_name': '품명', 'quantity': '수량', 'unit': '규격', 'color': '색상',
                'weaving_date': '제직일', 'dyeing_date': '염색일', 'sewing_date': '봉제일', 
                'shipping_date': '출고일', 'shipping_method': '출고방법', 'shipping_dest_name': '출고지',
                'delivery_date': '납품요청일', 'note': '비고'
            }
            
            # 존재하는 컬럼만 선택
            avail_cols = [c for c in cols_client.keys() if c in df.columns]
            df_show = df[avail_cols].rename(columns=cols_client).fillna("")
            
            st.dataframe(
                df_show, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "수량": st.column_config.NumberColumn(format="%d"),
                }
            )
        else:
            st.info("데이터가 없습니다.")

    # --- 등록 탭 ---
    with tab_reg:
        st.markdown("##### 발주 정보 입력")
        with st.form("order_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            client_name = c1.text_input("업체명 (필수)")
            product_name = c2.text_input("품명 (필수)")
            
            c3, c4, c5 = st.columns(3)
            quantity = c3.number_input("수량", min_value=0, step=10)
            spec = c4.text_input("규격")
            color = c5.text_input("색상")
            
            c6, c7, c8 = st.columns(3)
            yarn = c6.text_input("사종")
            weight = c7.text_input("중량")
            otype = c8.selectbox("구분", ["신규", "추가", "샘플"])
            
            c9, c10 = st.columns(2)
            manager = c9.text_input("담당자")
            contact = c10.text_input("연락처")
            
            c11, c12 = st.columns(2)
            odate = c11.date_input("발주일", datetime.date.today())
            ddate = c12.date_input("납품요청일", datetime.date.today() + datetime.timedelta(days=7))
            
            st.markdown("---")
            st.caption("추가 정보")
            c13, c14, c15 = st.columns(3)
            weaving = c13.text_input("제직 정보")
            dyeing = c14.text_input("염색 정보")
            site = c15.text_input("작업지")
            
            c16, c17 = st.columns(2)
            dest = c16.text_input("운송처")
            note = c17.text_input("비고")
            
            if st.form_submit_button("발주 등록 완료"):
                if client_name and product_name:
                    new_doc = {
                        "client_name": client_name, "product_name": product_name, "quantity": quantity,
                        "unit": spec, "color": color, "yarn_type": yarn, "weight": weight,
                        "order_type": otype, "manager": manager, "contact": contact,
                        "order_date": str(odate), "delivery_date": str(ddate),
                        "weaving": weaving, "dyeing": dyeing, "work_site": site,
                        "delivery_to": dest, "note": note,
                        "status": "발주접수", "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    db.collection("production_orders").add(new_doc)
                    st.success("등록되었습니다.")
                    st.rerun()
                else:
                    st.error("업체명과 품명을 입력해주세요.")

# ==========================================
# VIEW 2: 관리자용
# ==========================================
elif menu == "관리자용 (공정 관리)":
    st.title("🛠️ 관리자 모드")
    
    tab_list, tab_upload = st.tabs(["📋 발주 관리", "📤 엑셀 업로드"])
    
    # --- 발주 관리 탭 ---
    with tab_list:
        df = load_data()
        if not df.empty:
            # 1. 필터링
            with st.expander("🔍 검색 및 필터", expanded=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                
                # 날짜 필터
                df['dt_obj'] = pd.to_datetime(df['order_date'], errors='coerce').dt.date
                min_d = df['dt_obj'].min() if pd.notnull(df['dt_obj'].min()) else datetime.date.today()
                dates = c1.date_input("발주 기간", [min_d, datetime.date.today()])
                
                # 상태 필터
                all_stats = list(df['status'].unique()) if 'status' in df.columns else []
                sel_stats = c2.multiselect("진행상태", [x for x in all_stats if isinstance(x, str)])
                
                # 텍스트 검색
                txt_search = c3.text_input("통합 검색", placeholder="업체, 품명...")

            # 필터 적용 logic
            mask = pd.Series(True, index=df.index)
            if len(dates) == 2:
                mask &= (df['dt_obj'] >= dates[0]) & (df['dt_obj'] <= dates[1])
            if sel_stats:
                mask &= df['status'].isin(sel_stats)
            if txt_search:
                mask &= (
                    df['client_name'].astype(str).str.contains(txt_search) | 
                    df['product_name'].astype(str).str.contains(txt_search)
                )
            
            df_filtered = df[mask].copy()
            
            # 2. 데이터 에디터 (선택용)
            st.markdown(f"**총 {len(df_filtered)}건**")
            
            # 선택 컬럼 추가
            if 'selected' not in df_filtered.columns:
                df_filtered.insert(0, 'selected', False)
            
            # 컬럼 순서 및 이름
            col_map_admin = {
                'selected': '선택', 'status': '진행상태', 'client_name': '업체명', 'product_name': '품명',
                'quantity': '수량', 'order_date': '발주일', 'delivery_date': '납품일',
                'weaving_date': '제직일', 'dyeing_date': '염색일', 'sewing_date': '봉제일', 'shipping_date': '출고일',
                'manager': '담당자', 'work_site': '작업지', 'note': '비고'
            }
            
            # 표시할 컬럼만 추출
            disp_cols = [c for c in col_map_admin.keys() if c in df_filtered.columns]
            df_display = df_filtered[disp_cols + ['id']].rename(columns=col_map_admin) # ID 유지
            
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "선택": st.column_config.CheckboxColumn(width="small"),
                    "수량": st.column_config.NumberColumn(format="%d"),
                    "id": None # ID 숨김
                },
                disabled=[c for c in df_display.columns if c != "선택"],
                hide_index=True,
                use_container_width=True,
                key="admin_editor"
            )
            
            # 3. 일괄 업데이트 액션
            st.markdown("### ⚡ 일괄 업데이트")
            with st.form("bulk_action"):
                c1, c2, c3, c4 = st.columns(4)
                act_date = c1.date_input("적용 날짜", datetime.date.today())
                act_stage = c2.selectbox("변경할 공정", ["제직공정", "염색공정", "봉제공정", "출고완료"])
                
                # 출고 옵션
                act_method = c3.selectbox("출고 방법 (출고시)", ["-", "택배", "화물", "용차", "직배송"])
                act_dest = c4.text_input("출고지명 (출고시)")
                
                if st.form_submit_button("선택 항목 적용"):
                    sel_rows = edited_df[edited_df["선택"]]
                    if not sel_rows.empty:
                        cnt = 0
                        upd_data = {
                            "status": act_stage,
                            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        d_str = str(act_date)
                        
                        if act_stage == "제직공정": upd_data["weaving_date"] = d_str
                        elif act_stage == "염색공정": upd_data["dyeing_date"] = d_str
                        elif act_stage == "봉제공정": upd_data["sewing_date"] = d_str
                        elif act_stage == "출고완료":
                            upd_data["shipping_date"] = d_str
                            if act_method != "-": upd_data["shipping_method"] = act_method
                            if act_dest: upd_data["shipping_dest_name"] = act_dest
                        
                        for idx, row in sel_rows.iterrows():
                            # ID로 업데이트
                            db.collection("production_orders").document(row['id']).update(upd_data)
                            cnt += 1
                        st.success(f"{cnt}건 처리 완료")
                        st.rerun()
                    else:
                        st.warning("선택된 항목이 없습니다.")
            
            # 4. 엑셀 다운로드 & 삭제
            st.divider()
            c_down, c_del = st.columns([1, 1])
            with c_down:
                # 엑셀 다운로드
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_display.drop(columns=['선택', 'id'], errors='ignore').to_excel(writer, index=False)
                st.download_button("📥 현재 목록 엑셀 다운로드", buffer.getvalue(), "orders.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
            with c_del:
                with st.expander("🗑️ 데이터 전체 삭제 (주의)"):
                    if st.button("모든 데이터 삭제", type="primary"):
                        all_docs = db.collection("production_orders").stream()
                        for d in all_docs: d.reference.delete()
                        st.success("삭제됨")
                        st.rerun()

        else:
            st.info("데이터가 없습니다.")

    # --- 엑셀 업로드 탭 ---
    with tab_upload:
        st.info("엑셀 헤더 예시: 업체명, 품명, 발주수량, 발주일, 납품일, 규격, 색상...")
        up_file = st.file_uploader("파일 선택", type=['xlsx', 'xls'])
        if up_file:
            df_up = pd.read_excel(up_file)
            # 헤더 정리
            df_up.columns = [str(c).strip().replace('\n',' ') for c in df_up.columns]
            st.dataframe(df_up.head())
            
            if st.button("DB에 저장하기"):
                bar = st.progress(0)
                for i, row in df_up.iterrows():
                    def s(k): return str(row.get(k, "")).strip()
                    def d(k):
                        v = row.get(k)
                        if pd.isna(v) or v=="": return ""
                        try: return pd.to_datetime(v).strftime("%Y-%m-%d")
                        except: return str(v)
                    
                    doc = {
                        "client_name": s("업체명"), "product_name": s("품명"), "quantity": row.get("발주수량", 0),
                        "unit": s("규격"), "order_date": d("발주일") or datetime.date.today().strftime("%Y-%m-%d"),
                        "delivery_date": d("납품일"), "delivery_to": s("운송처"), "manager": s("발주담당자"),
                        "order_type": s("구분(신규/추가)"), "work_site": s("작업지"), "weaving": s("제직"),
                        "dyeing": s("염색"), "weight": s("중량"), "yarn_type": s("사종"), "color": s("색상"),
                        "contact": s("연락처"), "email_sent_date": d("e-mail 발송일"), "note": s("비 고"),
                        "status": "발주접수", "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    db.collection("production_orders").add(doc)
                    bar.progress((i+1)/len(df_up))
                st.success("업로드 완료!")
                st.rerun()
