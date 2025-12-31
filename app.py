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
st.title("🏭 아티스린넨 공정 관리 시스템")
st.markdown("---")

# 탭 구성: 조회용(거래처) / 입력용(관리자)
tab1, tab2 = st.tabs(["🔍 진행상황 조회 (거래처용)", "🛠️ 작업내역 입력 (관리자용)"])

# ==========================================
# 탭 1: 거래처 조회 화면
# ==========================================
with tab1:
    st.subheader("📦 발주 등록 및 조회")
    
    # 🔒 보안: 접속 코드 확인
    access_code = st.text_input("🔒 접속 코드를 입력하세요 (거래처용)", type="password", key="access_code")
    
    if access_code == "1234":  # 👈 원하는 비밀번호로 변경하세요
        
        # --- 1. 신규 발주 등록 (거래처용으로 이동) ---
        with st.expander("📝 신규 발주 등록하기", expanded=False):
            with st.form("new_order_form_client", clear_on_submit=True):
                st.caption("발주 내용을 입력해주세요.")
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
                quantity = c9.number_input("발주수량", min_value=0, step=10)
                weight = c10.text_input("중량 (숫자만 입력)", help="10단위 입력 권장") # 텍스트로 입력받거나 number_input 사용
                order_date = c11.date_input("발주일", datetime.datetime.now())
                delivery_date = c12.date_input("납품일", datetime.datetime.now() + datetime.timedelta(days=7))
                
                # 4열
                c13, c14, c15 = st.columns(3)
                weaving = c13.text_input("제직 정보")
                dyeing = c14.text_input("염색 정보")
                work_site = c15.text_input("작업지")
                
                # 5열
                c16, c17, c18 = st.columns(3)
                delivery_to = c16.text_input("운송처")
                email_date = c17.date_input("e-mail 발송일", value=None)
                note = c18.text_input("비고")
                
                submitted = st.form_submit_button("발주 등록")
                
                if submitted and client_name and product_name:
                    new_data = {
                        "client_name": client_name,
                        "product_name": product_name,
                        "quantity": quantity,
                        "unit": spec,
                        "color": color,
                        "yarn_type": yarn_type,
                        "weight": weight,
                        "order_type": order_type,
                        "manager": manager,
                        "contact": contact,
                        "weaving": weaving,
                        "dyeing": dyeing,
                        "work_site": work_site,
                        "delivery_to": delivery_to,
                        "email_sent_date": email_date.strftime("%Y-%m-%d") if email_date else "",
                        "note": note,
                        "order_date": order_date.strftime("%Y-%m-%d"),
                        "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                        "status": "발주접수",
                        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    db.collection("production_orders").add(new_data)
                    st.success("발주가 성공적으로 등록되었습니다.")
                    st.rerun()

        st.divider()
        
        # --- 2. 진행상황 조회 ---
        # 검색 기능
        col1, col2 = st.columns([3, 1])
        search_term = col1.text_input("발주처명 또는 품명을 입력하세요", placeholder="예: ABC물산")
        search_btn = col2.button("조회하기")

        # 데이터 가져오기
        orders_ref = db.collection("production_orders")
        query = orders_ref.order_by("order_date", direction=firestore.Query.DESCENDING)
        
        # 검색어가 있으면 필터링
        data_list = []
        try:
            docs = query.stream()
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                if not search_term or (search_term in d.get('client_name', '')) or (search_term in d.get('product_name', '')):
                    data_list.append(d)
        except Exception:
            st.warning("⚠️ 데이터베이스 연결이 지연되고 있습니다. 잠시 후 다시 조회해주세요.")

        if data_list:
            # 데이터프레임 변환
            client_df = pd.DataFrame(data_list)
            
            # 컬럼 매핑 및 순서 정의 (거래처용)
            client_col_map = {
                'status': '진행상태',
                'order_date': '발주일',
                'client_name': '업체명',
                'product_name': '품명',
                'quantity': '수량',
                'unit': '규격',
                'color': '색상',
                'weaving_date': '제직일',
                'dyeing_date': '염색일',
                'sewing_date': '봉제일',
                'shipping_date': '출고일',
                'shipping_method': '출고방법',
                'shipping_dest_name': '출고지',
                'delivery_date': '납품요청일',
                'note': '비고'
            }
            
            # 표시할 컬럼만 선택 및 정렬
            display_cols = [c for c in client_col_map.keys() if c in client_df.columns]
            client_display_df = client_df[display_cols].rename(columns=client_col_map)
            
            # 빈 값 처리
            client_display_df = client_display_df.fillna("")
            
            st.dataframe(
                client_display_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "진행상태": st.column_config.TextColumn("진행상태", width="medium"),
                    "발주일": st.column_config.DateColumn("발주일", format="YYYY-MM-DD"),
                    "납품요청일": st.column_config.DateColumn("납품요청일", format="YYYY-MM-DD"),
                    "제직일": st.column_config.DateColumn("제직일", format="YYYY-MM-DD"),
                    "염색일": st.column_config.DateColumn("염색일", format="YYYY-MM-DD"),
                    "봉제일": st.column_config.DateColumn("봉제일", format="YYYY-MM-DD"),
                    "출고일": st.column_config.DateColumn("출고일", format="YYYY-MM-DD"),
                    "수량": st.column_config.NumberColumn("수량", format="%d"),
                }
            )
        else:
            st.info("조회된 내역이 없습니다.")
    else:
        st.info("🔒 내역을 조회하려면 접속 코드를 입력해주세요. (초기 비밀번호: 1234)")

# ==========================================
# 탭 2: 관리자 입력 화면
# ==========================================
with tab2:
    st.subheader("📤 엑셀 일괄 업로드")
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
                
                # 날짜 변환 헬퍼 함수
                def parse_date(date_val):
                    if pd.isna(date_val) or date_val == "":
                        return ""
                    try:
                        # pandas의 강력한 날짜 파싱 기능 사용
                        return pd.to_datetime(date_val).strftime("%Y-%m-%d")
                    except:
                        return str(date_val) # 파싱 실패 시 원본 유지

                for idx, row in df.iterrows():
                    # 엑셀 데이터 매핑
                    # (값이 없으면 빈 문자열이나 0으로 처리)
                    doc_data = {
                        "client_name": str(row.get("업체명", "")),
                        "product_name": str(row.get("품명", "")),
                        "quantity": row.get("발주수량", 0),
                        "unit": str(row.get("규격", "yds")), # 규격을 단위로 사용
                        "order_date": parse_date(row.get("발주일")) or datetime.datetime.now().strftime("%Y-%m-%d"),
                        "delivery_date": parse_date(row.get("납품일")),
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
                        "email_sent_date": parse_date(row.get("e-mail 발송일")),
                        "note": str(row.get("비 고", "")),
                        "status": "발주접수",
                        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # 날짜 형식이 datetime 객체인 경우 문자열로 변환
                    # (위의 parse_date 함수에서 이미 처리했으므로 중복 제거 가능하지만 안전을 위해 유지)
                    # for key, val in doc_data.items(): ... 

                    db.collection("production_orders").add(doc_data)
                    success_count += 1
                    progress_bar.progress((idx + 1) / len(df))
                
                st.success(f"총 {success_count}건의 데이터가 저장되었습니다!")
                st.rerun()
                
        except Exception as e:
            st.error(f"엑셀 처리 중 오류가 발생했습니다: {e}")

    st.divider()
    st.subheader("📋 발주 내역 관리 및 공정 업데이트")
    
    # 전체 데이터 불러오기
    data = []
    try:
        orders = db.collection("production_orders").order_by("order_date", direction=firestore.Query.DESCENDING).stream()
        for doc in orders:
            d = doc.to_dict()
            d['id'] = doc.id
            data.append(d)
    except Exception:
        st.warning("⚠️ 데이터베이스 연결이 지연되고 있습니다. 잠시 후 다시 시도해주세요.")
    
    if data:
        df = pd.DataFrame(data)
        # 선택 기능을 위해 'selected' 컬럼 추가 (기본값 False)
        # 맨 앞에 삽입하기 위해 insert 사용
        if 'selected' not in df.columns:
            df.insert(0, 'selected', False)
        
        # 날짜 변환 (문자열 -> datetime64 -> 시간제거)
        # astype(str)을 추가하여 데이터가 숫자로 들어와도 안전하게 처리
        df['order_date_dt'] = pd.to_datetime(df['order_date'].astype(str), errors='coerce').dt.normalize()
        
        # 초기 기간 설정 (최근 3개월)
        today = datetime.date.today()
        three_months_ago = today - datetime.timedelta(days=90)
        
        # 1. 상시 표시 필터 (기간, 진행상태)
        c1, c2 = st.columns([1, 2])
        # min_value, max_value 제한을 없애서 선택 시 초기화되는 문제 해결
        date_range = c1.date_input("발주기간", [three_months_ago, today], key="filter_date")
        
        status_options = df['status'].unique().tolist() if 'status' in df.columns else []
        status_options = [x for x in status_options if x]
        selected_status = c2.multiselect("진행상태", status_options, key="filter_status")

        # 2. 상세 검색 조건 (Expander)
        with st.expander("➕ 상세 검색 조건 설정"):
            filter_cols = {
                "client_name": "업체명",
                "product_name": "품명",
                "manager": "발주담당자",
                "order_type": "구분(신규/추가)",
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
            # Timestamp로 변환하여 datetime64 컬럼과 비교 (TypeError 방지)
            start_ts = pd.Timestamp(start_d)
            end_ts = pd.Timestamp(end_d)
            
            filtered_df = filtered_df[
                (filtered_df['order_date_dt'] >= start_ts) & 
                (filtered_df['order_date_dt'] <= end_ts)
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
        
        # --- 일괄 업데이트 UI ---
        st.markdown("### 🛠️ 공정 단계 일괄 업데이트")
        st.caption("아래 목록에서 업데이트할 항목을 체크(✅)하고, 적용할 날짜와 공정을 선택하세요.")
        
        # 데이터 에디터 (체크박스 포함) - 폼 밖으로 이동하여 안정성 확보
        edited_df = st.data_editor(
            display_df[final_cols],
            column_config={
                "선택": st.column_config.CheckboxColumn(
                    "선택",
                    help="업데이트할 항목을 선택하세요",
                    default=False,
                    width="small"
                ),
                "발주일": st.column_config.DateColumn("발주일", format="YYYY-MM-DD"),
                "납품일": st.column_config.DateColumn("납품일", format="YYYY-MM-DD"),
                "e-mail 발송일": st.column_config.DateColumn("e-mail 발송일", format="YYYY-MM-DD"),
                "제직일": st.column_config.DateColumn("제직일", format="YYYY-MM-DD"),
                "염색일": st.column_config.DateColumn("염색일", format="YYYY-MM-DD"),
                "봉제일": st.column_config.DateColumn("봉제일", format="YYYY-MM-DD"),
                "출고일": st.column_config.DateColumn("출고일", format="YYYY-MM-DD"),
                "발주수량": st.column_config.NumberColumn("발주수량", format="%d"),
            },
            # 선택 컬럼 외에는 수정 불가 (나머지 컬럼들은 모두 disabled 리스트에 추가)
            disabled=[c for c in final_cols if c != "선택"],
            hide_index=True,
            use_container_width=True,
            key="data_editor_bulk"
        )

        # 업데이트 설정 폼
        with st.form("bulk_update_form"):
            c1, c2, c3 = st.columns([1, 1, 1])
            update_date = c1.date_input("적용일자", datetime.date.today())
            target_stage = c2.selectbox("진행 공정 선택", ["제직공정", "염색공정", "봉제공정", "출고완료"])
            
            # 출고완료 선택 시 추가 입력창
            shipping_method = None
            shipping_dest = None
            
            # 폼 안에서는 동적 UI가 제한적이므로, 출고 관련 정보는 항상 입력받되 '출고완료'일 때만 저장하도록 처리
            c3.markdown("**[출고 시 입력]**")
            shipping_method = c3.selectbox("출고방법", ["-", "택배", "화물", "용차", "직배송"])
            shipping_dest = st.text_input("출고지명 (출고 시 입력)")
            
            update_submitted = st.form_submit_button("선택한 항목 일괄 적용")
            
            if update_submitted:
                # 선택된 행 찾기
                # 한글 컬럼명 '선택'으로 필터링
                selected_rows = edited_df[edited_df["선택"] == True]
                
                if not selected_rows.empty:
                    count = 0
                    update_data = {
                        "status": target_stage,
                        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # 공정별 날짜 필드 매핑
                    date_str = update_date.strftime("%Y-%m-%d")
                    if target_stage == "제직공정":
                        update_data["weaving_date"] = date_str
                    elif target_stage == "염색공정":
                        update_data["dyeing_date"] = date_str
                    elif target_stage == "봉제공정":
                        update_data["sewing_date"] = date_str
                    elif target_stage == "출고완료":
                        update_data["shipping_date"] = date_str
                        if shipping_method != "-":
                            update_data["shipping_method"] = shipping_method
                        if shipping_dest:
                            update_data["shipping_dest_name"] = shipping_dest
                    
                    # DB 업데이트
                    for idx, row in selected_rows.iterrows():
                        # 원본 데이터프레임(filtered_df)에서 ID를 찾아야 함
                        # 현재 row는 display_df의 행이므로 인덱스가 일치한다고 가정하거나 매핑 필요
                        # display_df는 filtered_df를 가공한 것이므로 인덱스가 동일함 (reset_index 안함)
                        original_id = filtered_df.iloc[idx]['id']
                        db.collection("production_orders").document(original_id).update(update_data)
                        count += 1
                    
                    st.success(f"✅ 총 {count}건의 상태가 '{target_stage}'(으)로 업데이트되었습니다.")
                    st.rerun()
                else:
                    st.warning("⚠️ 업데이트할 항목을 목록에서 선택(체크)해주세요.")
        
        # 데이터 초기화 버튼 (위험하므로 Expander 안에 숨김)
        st.divider()
        with st.expander("⚠️ 데이터 관리 (초기화)"):
            st.warning("주의: 이 버튼을 누르면 등록된 모든 발주 내역이 영구적으로 삭제됩니다.")
            if st.button("🗑️ 기존 데이터 전체 삭제하기", type="primary"):
                with st.spinner("데이터 삭제 중..."):
                    # 배치 삭제 (문서가 많을 경우를 대비)
                    docs = db.collection("production_orders").stream()
                    deleted_count = 0
                    for doc in docs:
                        doc.reference.delete()
                        deleted_count += 1
                st.success(f"총 {deleted_count}건의 데이터가 삭제되었습니다.")
                st.rerun()

    else:
        st.info("등록된 데이터가 없습니다.")