import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime
import pandas as pd
import json
import os

# 1. 페이지 설정 (반드시 가장 윗줄에 있어야 함)
st.set_page_config(page_title="아티스린넨 공정 관리", layout="wide", page_icon="🏭")

# 2. 데이터베이스 연결
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = None
        # 1) Streamlit Cloud Secrets 확인
        try:
            if "FIREBASE_KEY" in st.secrets:
                secrets_val = st.secrets["FIREBASE_KEY"]
                # 문자열이면 JSON 파싱, 딕셔너리면 바로 사용
                if isinstance(secrets_val, str):
                    key_dict = json.loads(secrets_val, strict=False)
                else:
                    key_dict = dict(secrets_val)
                
                # 줄바꿈 문자 처리
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(key_dict)
        except Exception:
            pass
        
        # 2) 로컬 파일 확인
        if cred is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            key_path = os.path.join(current_dir, "serviceAccountKey.json")
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
        
        if cred:
            firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = get_db()
except Exception as e:
    st.error(f"데이터베이스 연결 실패: {e}")
    st.stop()

# 메인 타이틀
st.title("🏭 아티스린넨 공정 관리 시스템")

# 탭 구성
tab1, tab2 = st.tabs(["🔍 거래처 조회/등록", "🛠️ 관리자 모드"])

# ==========================================
# Tab 1: 거래처 (조회 및 등록)
# ==========================================
with tab1:
    st.subheader("📦 발주 등록 및 조회")
    access_code = st.text_input("🔒 접속 코드 (거래처용)", type="password", key="client_pw")
    
    if access_code == "1234":
        # --- 신규 발주 등록 ---
        with st.expander("📝 신규 발주 등록하기"):
            with st.form("client_order_form", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns(4)
                client_name = c1.text_input("업체명 (필수)")
                manager = c2.text_input("발주담당자")
                order_type = c3.selectbox("구분", ["신규", "추가", "샘플"])
                contact = c4.text_input("연락처")
                
                c5, c6, c7, c8 = st.columns(4)
                product_name = c5.text_input("품명 (필수)")
                color = c6.text_input("색상")
                spec = c7.text_input("규격")
                yarn_type = c8.text_input("사종")
                
                c9, c10, c11, c12 = st.columns(4)
                quantity = c9.number_input("발주수량", min_value=0, step=10)
                weight = c10.text_input("중량")
                order_date = c11.date_input("발주일", datetime.date.today())
                delivery_date = c12.date_input("납품일", datetime.date.today() + datetime.timedelta(days=7))
                
                c13, c14, c15 = st.columns(3)
                weaving = c13.text_input("제직 정보")
                dyeing = c14.text_input("염색 정보")
                work_site = c15.text_input("작업지")
                
                c16, c17, c18 = st.columns(3)
                delivery_to = c16.text_input("운송처")
                email_date = c17.date_input("e-mail 발송일", value=None)
                note = c18.text_input("비고")
                
                if st.form_submit_button("발주 등록"):
                    if client_name and product_name:
                        doc = {
                            "client_name": client_name, "product_name": product_name, "quantity": quantity,
                            "unit": spec, "color": color, "yarn_type": yarn_type, "weight": weight,
                            "order_type": order_type, "manager": manager, "contact": contact,
                            "weaving": weaving, "dyeing": dyeing, "work_site": work_site,
                            "delivery_to": delivery_to, "note": note, "status": "발주접수",
                            "order_date": str(order_date), "delivery_date": str(delivery_date),
                            "email_sent_date": str(email_date) if email_date else "",
                            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        db.collection("production_orders").add(doc)
                        st.success("등록되었습니다.")
                        st.rerun()
                    else:
                        st.error("업체명과 품명은 필수 입력 항목입니다.")

        # --- 조회 기능 ---
        st.divider()
        search_txt = st.text_input("검색 (업체명 또는 품명)", placeholder="엔터 입력")
        
        # 데이터 로드
        docs = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
        data = []
        for d in docs:
            dd = d.to_dict()
            if not search_txt or (search_txt in dd.get('client_name','')) or (search_txt in dd.get('product_name','')):
                data.append(dd)
        
        if data:
            df = pd.DataFrame(data)
            # 컬럼 매핑 (거래처용)
            col_map = {
                'status': '진행상태', 'order_date': '발주일', 'client_name': '업체명', 'product_name': '품명',
                'quantity': '수량', 'unit': '규격', 'color': '색상', 'weaving_date': '제직일',
                'dyeing_date': '염색일', 'sewing_date': '봉제일', 'shipping_date': '출고일',
                'delivery_date': '납품요청일', 'note': '비고'
            }
            # 존재하는 컬럼만 선택
            cols = [c for c in col_map if c in df.columns]
            show_df = df[cols].rename(columns=col_map).fillna("")
            
            st.dataframe(show_df, use_container_width=True, hide_index=True)
        else:
            st.info("조회된 데이터가 없습니다.")

# ==========================================
# Tab 2: 관리자 (엑셀 업로드 & 일괄 관리)
# ==========================================
with tab2:
    st.subheader("📤 엑셀 업로드")
    up_file = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xls'])
    
    if up_file:
        df_up = pd.read_excel(up_file)
        # 컬럼명 공백/줄바꿈 정리
        df_up.columns = [str(c).strip().replace('\n',' ') for c in df_up.columns]
        st.dataframe(df_up.head())
        
        if st.button("DB 저장"):
            bar = st.progress(0)
            for i, row in df_up.iterrows():
                # 안전한 문자열 변환 함수
                def s(k): return str(row.get(k, "")).strip()
                # 안전한 날짜 변환 함수
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
            st.success("저장 완료!")
            st.rerun()

    st.divider()
    st.subheader("📋 발주 관리 및 공정 업데이트")
    
    # 전체 데이터 로드
    docs = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
    data = [{"id": d.id, **d.to_dict()} for d in docs]
    
    if data:
        df = pd.DataFrame(data)
        if 'selected' not in df.columns: df.insert(0, 'selected', False)
        
        # 날짜 필터링을 위한 임시 컬럼
        df['dt'] = pd.to_datetime(df['order_date'], errors='coerce').dt.normalize()
        
        # 필터 UI
        c1, c2 = st.columns([1, 2])
        def_start = datetime.date.today() - datetime.timedelta(days=90)
        dates = c1.date_input("기간", [def_start, datetime.date.today()])
        
        stats = [x for x in df['status'].unique() if x] if 'status' in df.columns else []
        sel_stats = c2.multiselect("상태", stats)
        
        # 필터 적용
        mask = pd.Series(True, index=df.index)
        if len(dates)==2:
            s, e = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
            mask &= (df['dt'] >= s) & (df['dt'] <= e)
        if sel_stats:
            mask &= df['status'].isin(sel_stats)
            
        df_show = df[mask].copy()
        
        # 컬럼 매핑 (관리자용)
        col_map = {
            'selected': '선택', 'status': '진행상태', 'email_sent_date': 'e-mail 발송일',
            'order_type': '구분', 'manager': '발주담당자', 'order_date': '발주일',
            'delivery_date': '납품일', 'work_site': '작업지', 'client_name': '업체명',
            'weaving': '제직(정보)', 'dyeing': '염색(정보)', 'quantity': '발주수량',
            'unit': '규격', 'product_name': '품명', 'weight': '중량', 'yarn_type': '사종',
            'color': '색상', 'delivery_to': '운송처', 'contact': '연락처', 'note': '비고',
            'weaving_date': '제직일', 'dyeing_date': '염색일', 'sewing_date': '봉제일',
            'shipping_date': '출고일', 'shipping_method': '출고방법', 'shipping_dest_name': '출고지명'
        }
        
        # 표시할 컬럼 순서
        disp_cols = ['selected', 'status', 'email_sent_date', 'order_type', 'manager', 'order_date', 
                     'delivery_date', 'work_site', 'client_name', 'weaving', 'dyeing', 'quantity', 
                     'unit', 'product_name', 'weight', 'yarn_type', 'color', 'delivery_to', 'contact', 
                     'note', 'weaving_date', 'dyeing_date', 'sewing_date', 'shipping_date', 
                     'shipping_method', 'shipping_dest_name']
        
        # 실제 존재하는 컬럼만 매핑
        final_cols = []
        for c in disp_cols:
            if c in df_show.columns:
                df_show.rename(columns={c: col_map[c]}, inplace=True)
                final_cols.append(col_map[c])
        
        # ID 컬럼은 숨김 처리 위해 따로 보관 (업데이트용)
        # df_show에는 'id' 컬럼이 남아있음
        
        # 데이터 에디터 (폼 밖으로 뺌 -> 안정성 확보)
        edited = st.data_editor(
            df_show[final_cols + ['id']], # ID 포함해서 전달
            column_config={
                "선택": st.column_config.CheckboxColumn(width="small"),
                "발주수량": st.column_config.NumberColumn(format="%d"),
                "id": None # ID 컬럼은 화면에서 숨김
            },
            disabled=[c for c in final_cols if c != "선택"], # 선택 외 수정 불가
            hide_index=True,
            use_container_width=True,
            key="editor"
        )
        
        # 일괄 업데이트 폼
        with st.form("update_form"):
            c1, c2, c3 = st.columns(3)
            u_date = c1.date_input("적용일자", datetime.date.today())
            u_stage = c2.selectbox("공정", ["제직공정", "염색공정", "봉제공정", "출고완료"])
            
            c3.markdown("**출고 정보**")
            ship_method = c3.selectbox("방법", ["-", "택배", "화물", "용차", "직배송"])
            ship_dest = st.text_input("출고지명")
            
            if st.form_submit_button("선택 항목 일괄 적용"):
                # 선택된 행 필터링
                sel_rows = edited[edited["선택"]]
                
                if not sel_rows.empty:
                    cnt = 0
                    upd = {"status": u_stage, "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    d_str = str(u_date)
                    
                    if u_stage == "제직공정": upd["weaving_date"] = d_str
                    elif u_stage == "염색공정": upd["dyeing_date"] = d_str
                    elif u_stage == "봉제공정": upd["sewing_date"] = d_str
                    elif u_stage == "출고완료":
                        upd["shipping_date"] = d_str
                        if ship_method != "-": upd["shipping_method"] = ship_method
                        if ship_dest: upd["shipping_dest_name"] = ship_dest
                    
                    for idx, row in sel_rows.iterrows():
                        doc_id = row['id'] # 숨겨진 ID 컬럼 사용
                        db.collection("production_orders").document(doc_id).update(upd)
                        cnt += 1
                    st.success(f"{cnt}건 업데이트 완료")
                    st.rerun()
                else:
                    st.warning("선택된 항목이 없습니다.")

    # 데이터 초기화
    with st.expander("⚠️ 데이터 초기화"):
        if st.button("전체 삭제", type="primary"):
            ls = db.collection("production_orders").stream()
            for d in ls: d.reference.delete()
            st.success("삭제 완료")
            st.rerun()
