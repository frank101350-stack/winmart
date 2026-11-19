import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import unicodedata

# --- 기본 설정 ---
st.set_page_config(page_title="Dữ Liệu Dashboard", layout="wide")

# --- 사이드바: 데이터 업로드 (멀티 파일) ---
st.sidebar.title("☁️ Tải lên dữ liệu")
st.sidebar.caption("Bạn có thể kéo thả nhiều tệp cùng lúc (여러 파일을 한 번에 드래그하세요)")

uploaded_files = st.sidebar.file_uploader("Chọn tệp Excel (Kéo thả nhiều tệp)", type=['xlsx', 'xls'], accept_multiple_files=True)

all_data = [] 

# 베트남어 성조 제거 및 소문자 변환 함수 (시트 이름을 유연하게 찾기 위함)
def normalize_text(text):
    if not isinstance(text, str):
        return str(text)
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8').lower()

if uploaded_files:
    for uploaded_file in uploaded_files:
        try:
            # 1. 파일명에서 연도/월 자동 추출
            match = re.search(r'tháng\s*(\d{1,2})\.?(\d{4})', uploaded_file.name.lower())
            if match:
                file_month = int(match.group(1))
                file_year = int(match.group(2))
            else:
                alt_match = re.search(r'^(20\d{2})(\d{2})', uploaded_file.name)
                if alt_match:
                    file_year = int(alt_match.group(1))
                    file_month = int(alt_match.group(2))
                else:
                    file_month = 1
                    file_year = 2025

            # 2. 엑셀 파일 읽기
            xls = pd.ExcelFile(uploaded_file)
            
            sales_sheet = None
            inv_sheet = None
            
            # 시트 이름 유연하게 찾기 (성조 무시)
            for sheet in xls.sheet_names:
                s_norm = normalize_text(sheet)
                if 'ban' in s_norm or '판매' in s_norm or 'sales' in s_norm:
                    sales_sheet = sheet
                elif 'ton' in s_norm or '재고' in s_norm or 'stock' in s_norm:
                    inv_sheet = sheet

            if sales_sheet and inv_sheet:
                # 데이터를 안전하게 처리하는 내부 함수
                def process_sheet(sheet_name, data_type):
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=1)
                    
                    # 필수 열(0, 1, 3, 5, 6) 추출
                    cols = [0, 1, 3, 5, 6]
                    df = df.iloc[:, cols]
                    df.columns = ['unit', 'region', 'supermarket', 'product', 'qty']
                    
                    # 텍스트 열 안전하게 변환 (에러 원인 해결)
                    for col in ['unit', 'region', 'supermarket', 'product']:
                        df[col] = df[col].astype(str)
                        # nan 문자열이나 빈칸을 'Khác(기타)'로 변경
                        df.loc[df[col] == 'nan', col] = 'Khác'
                        df.loc[df[col] == '', col] = 'Khác'
                        
                    # 수량 열 강제 숫자 변환
                    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
                    df['type'] = data_type
                    return df

                # 판매와 재고 각각 처리
                df_sales = process_sheet(sales_sheet, 'sales')
                df_inv = process_sheet(inv_sheet, 'inventory')

                # 병합 및 피벗
                df_combined = pd.concat([df_sales, df_inv], ignore_index=True)
                
                df_grouped = df_combined.pivot_table(
                    index=['unit', 'region', 'supermarket', 'product'], 
                    columns='type', values='qty', aggfunc='sum', fill_value=0
                ).reset_index()

                # 누락된 컬럼이 있을 경우 방지
                if 'sales' not in df_grouped.columns: df_grouped['sales'] = 0
                if 'inventory' not in df_grouped.columns: df_grouped['inventory'] = 0

                # 연도와 월 정보 추가
                df_grouped['year'] = file_year
                df_grouped['month'] = file_month

                # 리스트에 데이터 추가
                all_data.append(df_grouped)
            else:
                st.sidebar.error(f"❌ {uploaded_file.name}: Không tìm thấy sheet Bán/Tồn (판매/재고 시트를 찾을 수 없음)")
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi ({uploaded_file.name}): {e}")

# 업로드된 데이터들을 하나의 표로 합치기
if all_data:
    df = pd.concat(all_data, ignore_index=True)
else:
    df = pd.DataFrame(columns=['year', 'month', 'unit', 'region', 'supermarket', 'product', 'sales', 'inventory'])

# --- 메인 화면 ---
st.title("📊 Dữ Liệu Dashboard (Bán hàng & Tồn kho)")

if df.empty:
    st.info("Không có dữ liệu. Vui lòng kéo thả tệp Excel lên từ thanh bên trái.")
else:
    # --- 사이드바: 필터 ---
    st.sidebar.markdown("---")
    st.sidebar.title("🔍 Bộ lọc (필터)")
    
    def multiselect_filter(label, col_name):
        options = sorted(df[col_name].unique(), key=str)
        selected = st.sidebar.multiselect(label, options, default=[])
        return selected if selected else options

    f_year = multiselect_filter("Năm (연도)", "year")
    f_month = multiselect_filter("Tháng (월)", "month")
    f_unit = multiselect_filter("Đơn vị (UNIT)", "unit")
    f_region = multiselect_filter("Khu vực (지역)", "region")
    f_supermarket = multiselect_filter("Siêu thị", "supermarket")
    f_product = multiselect_filter("Sản phẩm (제품)", "product")

    # 필터 적용
    filtered_df = df[
        (df['year'].isin(f_year) if f_year else True) &
        (df['month'].isin(f_month) if f_month else True) &
        (df['unit'].isin(f_unit) if f_unit else True) &
        (df['region'].isin(f_region) if f_region else True) &
        (df['supermarket'].isin(f_supermarket) if f_supermarket else True) &
        (df['product'].isin(f_product) if f_product else True)
    ]

    # --- KPI 및 합계 계산 ---
    total_sales = filtered_df['sales'].sum()
    total_inv = filtered_df['inventory'].sum()
    stock_months = (total_inv / total_sales) if total_sales > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng số mục (필터링된 항목 수)", f"{len(filtered_df):,} mục")
    col2.metric("Tổng số lượng bán (총 판매)", f"{total_sales:,.0f}")
    col3.metric("Tổng tồn kho (총 재고)", f"{total_inv:,.0f}", f"{stock_months:.1f} tháng tồn")

    # --- 데이터 표 (상세 내역 대신 합계만 표시) ---
    st.subheader("Bảng tổng hợp (필터링된 데이터 합계)")
    
    summary_data = {
        'Phân loại (구분)': ['Tổng cộng (합계)'],
        'Tổng Bán (총 판매)': [f"{total_sales:,.0f}"],
        'Tổng Tồn kho (총 재고)': [f"{total_inv:,.0f}"],
        'Tháng tồn kho (재고개월수)': [f"{stock_months:.1f}"]
    }
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # --- 그래프 ---
    st.subheader("Biểu đồ xu hướng (월별 추이)")
    if not filtered_df.empty:
        trend_df = filtered_df.groupby(['year', 'month'])[['sales', 'inventory']].sum().reset_index()
        # 연도와 월 순서대로 정렬
        trend_df = trend_df.sort_values(by=['year', 'month'])
        trend_df['label'] = trend_df.apply(lambda x: f"T{int(x['month'])}/{int(x['year'])}", axis=1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=trend_df['label'], y=trend_df['inventory'], name='Tồn kho (재고)', marker_color='#f59e0b'))
        fig.add_trace(go.Scatter(x=trend_df['label'], y=trend_df['sales'], name='Bán hàng (판매)', mode='lines+markers', line=dict(color='#10b981', width=3)))
        
        fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
