import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime
import pandas as pd
import json
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="아티스린넨 발주내역", layout="wide", page_icon="🏭")

# 2. 데이터베이스 연결 (Firebase)
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        cred = None
        # 스트림릿 클라우드 배포용 (Secrets)
        try:
            if "FIREBASE_KEY" in st.secrets:
                secrets_val = st.secrets["FIREBASE_KEY"]
                try:
                    # 1. 문자열 형태(JSON String)로 들어온 경우 파싱
                    if isinstance(secrets_val, str):
                        key_dict = json.loads(secrets_val, strict=False)
                    # 2. 딕셔너리 형태(TOML 테이블)로 들어온 경우 바로 사용 (AttrDict 등)
                    else:
                        key_dict = dict(secrets_val)
                    
                    # 프로젝트 ID 검증: 실수로 옛날 키를 쓰는 경우 방지
                    if key_dict.get("project_id") == "sa-inventory":
                        st.error("🚨 잘못된 키 감지: 현재 'sa-inventory'(옛날 프로젝트) 키가 설정되어 있습니다. 'artispace' 키를 사용해주세요.")
                    
                    # private_key 줄바꿈 문자(\n) 처리 (매우 중요)
                    if "private_key" in key_dict:
                        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

                    cred = credentials.Certificate(key_dict)
                except Exception as e:
                    st.error(f"Secrets 설정 오류: {e} (키 값을 복사할 때 형식이 깨졌을 수 있습니다)")
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
st.title("아티스린넨 발주내역")
st.markdown("---")

# 탭 구성: 조회용(거래처) / 입력용(관리자)
tab1, tab2 = st.tabs(["🔍 진행상황 조회 (거래처용)", "🛠️ 작업내역 입력 (관리자용)"])

# ==========================================
# 탭 1: 거래처 조회 화면
# ==========================================
with tab1:
    st.subheader("📦 발주 건별 진행상황")
    
    # 🔒 보안: 접속 코드 확인
    access_code = st.text_input("🔒 접속 코드를 입력하세요 (거래처용)", type="password", key="access_code")
    
    if access_code == "1234":  # 👈 원하는 비밀번호로 변경하세요
        # 검색 기능
        col1, col2 = st.columns([3, 1])
        search_term = col1.text_input("발주처명 또는 품명을 입력하세요", placeholder="예: ABC물산")
        search_btn = col2.button("조회하기")

        # 데이터 가져오기
        orders_ref = db.collection("production_orders")
        query = orders_ref.order_by("order_date", direction=firestore.Query.DESCENDING)
        
        # 검색어가 있으면 필터링
        docs = query.stream()
        data_list = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            if not search_term or (search_term in d.get('client_name', '')) or (search_term in d.get('product_name', '')):
                data_list.append(d)

        if data_list:
            for item in data_list:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
                    c1.write(f"**발주처**: {item['client_name']}")
                    c2.write(f"**품명**: {item['product_name']}")
                    c3.write(f"**수량**: {item['quantity']} {item.get('unit', 'yds')}")
                    
                    current_stage = item['status']
                    try:
                        progress_idx = PROCESS_STAGES.index(current_stage)
                        progress_val = (progress_idx + 1) / len(PROCESS_STAGES)
                    except:
                        progress_val = 0
                    
                    c4.progress(progress_val, text=f"현재 상태: **{current_stage}**")
                    
                    with st.expander("상세 내역 보기"):
                        st.write(f"- 발주 일자: {item['order_date']}")
                        st.write(f"- 납품 예정처: {item.get('delivery_to', '-')}")
                        st.write(f"- 비고: {item.get('note', '-')}")
                        st.caption(f"최종 업데이트: {item.get('last_updated', '-')}")
        else:
            st.info("조회된 내역이 없습니다.")
    else:
        st.info("🔒 내역을 조회하려면 접속 코드를 입력해주세요. (초기 비밀번호: 1234)")

# ==========================================
# 탭 2: 관리자 입력 화면
# ==========================================
with tab2:
    st.subheader(" 엑셀 일괄 업로드")
    st.info("엑셀 파일의 첫 번째 줄(헤더)에 다음 항목들이 포함되어 있어야 합니다: 업체명, 품명, 발주수량, 발주일, 납품일, 규격, 색상 등")
    
    uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=['xlsx', 'xls'])
    
    if uploaded_file:
        try:
            # 엑셀 읽기
            df = pd.read_excel(uploaded_file)
            
            # 컬럼명 정리 (줄바꿈 제거 등)
            df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
            
            st.write("📊 데이터 미리보기 (상위 5개):")
            st.dataframe(df.head())
            
            if st.button("💾 엑셀 데이터 DB 저장하기"):
                progress_bar = st.progress(0)
                success_count = 0
                
                for idx, row in df.iterrows():
                    # 엑셀 데이터 매핑
                    # (값이 없으면 빈 문자열이나 0으로 처리)
                    doc_data = {
                        "client_name": str(row.get("업체명", "")),
                        "product_name": str(row.get("품명", "")),
                        "quantity": row.get("발주수량", 0),
                        "unit": str(row.get("규격", "yds")), # 규격을 단위로 사용
                        "order_date": row.get("발주일", datetime.datetime.now().strftime("%Y-%m-%d")),
                        "delivery_date": row.get("납품일", ""),
                        "delivery_to": str(row.get("운송처", "")),
                        "manager": str(row.get("발주담당자", "")),
                        "order_type": str(row.get("구분(신규/추가)", "")),
                        "work_site": str(row.get("작업지", "")),
                        "weaving": str(row.get("제직", "")),
                        "dyeing": str(row.get("염색", "")),
                        "weight": str(row.get("중량", "")),
                        "yarn_type": str(row.get("사종", "")),
                        "color": str(row.get("색상", "")),
                        "contact": str(row.get("연락처", "")),
                        "email_sent_date": row.get("e-mail 발송일", ""),
                        "note": str(row.get("비 고", "")),
                        "status": "발주접수",
                        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # 날짜 형식이 datetime 객체인 경우 문자열로 변환
                    for key, val in doc_data.items():
                        if isinstance(val, (datetime.datetime, datetime.date)):
                            doc_data[key] = val.strftime("%Y-%m-%d")

                    db.collection("production_orders").add(doc_data)
                    success_count += 1
                    progress_bar.progress((idx + 1) / len(df))
                
                st.success(f"총 {success_count}건의 데이터가 저장되었습니다!")
                st.rerun()
                
        except Exception as e:
            st.error(f"엑셀 처리 중 오류가 발생했습니다: {e}")

    st.divider()
    st.subheader("📝 신규 발주 등록 (개별 입력)")
    with st.form("new_order_form", clear_on_submit=True):
        # 1열
        c1, c2, c3, c4 = st.columns(4)
        client_name = c1.text_input("업체명 (필수)")
        manager = c2.text_input("발주담당자")
        order_type = c3.selectbox("구분", ["신규", "추가", "샘플"])
        contact = c4.text_input("연락처")
        
        # 2열
        c5, c6, c7, c8 = st.columns(4)
        product_name = c5.text_input("품명 (필수)")
        color = c6.text_input("색상")
        spec = c7.text_input("규격")
        yarn_type = c8.text_input("사종")
        
        # 3열
        c9, c10, c11, c12 = st.columns(4)
        quantity = c9.number_input("발주수량", min_value=1)
        weight = c10.text_input("중량")
        order_date = c11.date_input("발주일", datetime.datetime.now())
        delivery_date = c12.date_input("납품일", datetime.datetime.now() + datetime.timedelta(days=7))
        
        # 4열
        c13, c14, c15 = st.columns(3)
        weaving = c13.text_input("제직 정보")
        dyeing = c14.text_input("염색 정보")
        work_site = c15.text_input("작업지")
        
        # 5열
        c16, c17 = st.columns(2)
        delivery_to = c16.text_input("운송처")
        email_date = c17.date_input("e-mail 발송일", value=None)
        
        note = st.text_area("비 고")
        
        submitted = st.form_submit_button("발주 등록")
        
        if submitted and client_name and product_name:
            new_data = {
                "client_name": client_name,
                "product_name": product_name,
                "quantity": quantity,
                "unit": spec, # 규격을 단위로 사용
                "order_date": order_date.strftime("%Y-%m-%d"),
                "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                "delivery_to": delivery_to,
                "manager": manager,
                "order_type": order_type,
                "work_site": work_site,
                "weaving": weaving,
                "dyeing": dyeing,
                "weight": weight,
                "yarn_type": yarn_type,
                "color": color,
                "contact": contact,
                "email_sent_date": email_date.strftime("%Y-%m-%d") if email_date else "",
                "note": note,
                "status": "발주접수",  # 초기 상태
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            db.collection("production_orders").add(new_data)
            st.success("신규 발주가 등록되었습니다!")
            st.rerun()

    st.divider()
    st.subheader(" 발주 내역 조회 및 관리")
    
    # 전체 데이터 불러오기
    orders = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
    data = []
    for doc in orders:
        d = doc.to_dict()
        d['id'] = doc.id
        data.append(d)
    
    if data:
        df = pd.DataFrame(data)
        
        # 날짜 변환 (비교를 위해 date 객체로 변환)
        df['order_date_dt'] = pd.to_datetime(df['order_date'], errors='coerce')
        df['order_date_date'] = df['order_date_dt'].dt.date
        
        min_date = df['order_date_date'].min() if not df['order_date_date'].isnull().all() else datetime.date.today()
        max_date = df['order_date_date'].max() if not df['order_date_date'].isnull().all() else datetime.date.today()
        
        # 1. 상시 표시 필터 (기간, 진행상태)
        c1, c2 = st.columns([1, 2])
        date_range = c1.date_input("발주기간", [min_date, max_date], key="filter_date")
        
        status_options = df['status'].unique().tolist() if 'status' in df.columns else []
        status_options = [x for x in status_options if x]
        selected_status = c2.multiselect("진행상태", status_options, key="filter_status")

        # 2. 상세 검색 조건 (Expander)
        with st.expander("➕ 상세 검색 조건 설정"):
            filter_cols = {
                "client_name": "업체명",
                "product_name": "품명",
                "manager": "담당자",
                "order_type": "구분",
                "work_site": "작업지"
            }
            selected_filters = {}
            cols = st.columns(3)
            for i, (col_key, col_name) in enumerate(filter_cols.items()):
                unique_vals = df[col_key].unique().tolist() if col_key in df.columns else []
                unique_vals = [x for x in unique_vals if x]
                # key를 지정하여 리셋 문제 해결
                selected_filters[col_key] = cols[i % 3].multiselect(f"{col_name}", unique_vals, key=f"filter_{col_key}")

        # --- 필터 적용 ---
        filtered_df = df.copy()
        
        # 날짜 필터 적용
        if len(date_range) == 2:
            start_d, end_d = date_range
            # date 객체끼리 비교하여 오류 방지
            filtered_df = filtered_df[
                (filtered_df['order_date_date'] >= start_d) & 
                (filtered_df['order_date_date'] <= end_d)
            ]
        
        # 진행상태 필터 적용
        if selected_status:
            filtered_df = filtered_df[filtered_df['status'].isin(selected_status)]

        # 선택된 조건 표시용 텍스트
        active_conditions = []
        if len(date_range) == 2:
            active_conditions.append(f"📅 기간: {date_range[0]} ~ {date_range[1]}")
        if selected_status:
            active_conditions.append(f"진행상태: {', '.join(selected_status)}")

        # 다중 선택 필터 적용
        for col_key, selected_vals in selected_filters.items():
            if selected_vals:
                filtered_df = filtered_df[filtered_df[col_key].isin(selected_vals)]
                active_conditions.append(f"{filter_cols[col_key]}: {', '.join(selected_vals)}")
        
        # --- 결과 표시 ---
        st.divider()
        if active_conditions:
            st.info(f"✅ 적용된 조건: {' | '.join(active_conditions)}")
        else:
            st.info("✅ 전체 목록 조회 중")
            
        st.write(f"총 **{len(filtered_df)}**건의 내역이 있습니다.")
        
        # 정렬: 발주일 기준 내림차순 (기본)
        filtered_df = filtered_df.sort_values(by='order_date', ascending=False)
        
        # 컬럼명 한글 매핑
        col_map = {
            'order_date': '발주일',
            'client_name': '업체명',
            'product_name': '품명',
            'quantity': '수량',
            'unit': '규격',
            'status': '진행상태',
            'manager': '담당자',
            'delivery_date': '납품일',
            'delivery_to': '운송처',
            'note': '비고',
            'order_type': '구분',
            'work_site': '작업지',
            'weaving': '제직',
            'dyeing': '염색',
            'weight': '중량',
            'yarn_type': '사종',
            'color': '색상',
            'contact': '연락처',
            'email_sent_date': '이메일발송일'
        }
        
        # 표시할 컬럼 순서 지정 (중요한 것 먼저)
        display_order = [
            'order_date', 'client_name', 'product_name', 'quantity', 'unit', 'status', 
            'manager', 'delivery_date', 'delivery_to', 'work_site', 'order_type', 'note'
        ]
        
        # 매핑 적용 및 컬럼 필터링
        display_df = filtered_df.rename(columns=col_map)
        
        # 존재하는 컬럼만 선택하여 표시 (나머지 컬럼도 뒤에 붙여서 보여줌)
        mapped_display_order = [col_map[c] for c in display_order if c in filtered_df.columns]
        other_cols = [c for c in display_df.columns if c not in mapped_display_order and c not in ['id', 'order_date_dt', 'order_date_date']]
        
        final_cols = mapped_display_order + other_cols
        
        st.dataframe(display_df[final_cols], use_container_width=True, hide_index=True)

    else:
        st.info("등록된 데이터가 없습니다.")