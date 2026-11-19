import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import unicodedata

# --- 기본 설정 ---
st.set_page_config(page_title="Dữ Liệu Dashboard", layout="wide")

# --- 사이드바: 데이터 업로드 ---
st.sidebar.title("☁️ Tải lên dữ liệu")
st.sidebar.caption("Bạn có thể kéo thả nhiều tệp cùng lúc (여러 파일을 드래그하세요)")

uploaded_files = st.sidebar.file_uploader("Chọn tệp Excel", type=['xlsx', 'xls'], accept_multiple_files=True)

all_data = [] 

def normalize_text(text):
    if not isinstance(text, str):
        return str(text)
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8').lower()

if uploaded_files:
    for uploaded_file in uploaded_files:
        try:
            # 1. 파일명에서 월/연도 완벽 추출 (Tháng X 또는 TX 기준)
            match = re.search(r'(?:th[aá]ng|t)\s*(\d{1,2})(?:[\s./]*(\d{4}))?', uploaded_file.name.lower())
            if match:
                file_month = int(match.group(1))
                file_year = int(match.group(2)) if match.group(2) else 2025
            else:
                # 못 찾으면 파일명 첫 4자리를 연도로 추정, 월은 1월로 기본값
                year_match = re.search(r'(20\d{2})', uploaded_file.name)
                file_year = int(year_match.group(1)) if year_match else 2025
                file_month = 1

            # 2. 엑셀 파일 읽기
            xls = pd.ExcelFile(uploaded_file)
            
            sales_sheet = None
            inv_sheet = None
            
            for sheet in xls.sheet_names:
                s_norm = normalize_text(sheet)
                if 'ban' in s_norm or '판매' in s_norm or 'sales' in s_norm:
                    sales_sheet = sheet
                elif 'ton' in s_norm or '재고' in s_norm or 'stock' in s_norm:
                    inv_sheet = sheet

            if sales_sheet and inv_sheet:
                # --- 스마트 데이터 추출 함수 ---
                def process_sheet(sheet_name, data_type):
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=0)
                    if df.empty or len(df.columns) < 5:
                        return pd.DataFrame()
                        
                    cols = df.columns.tolist()
                    
                    # 1) Unit: 0번째 열
                    c_unit = cols[0]
                    # 2) Region: 'Region' 이 포함된 열
                    c_reg = next((c for c in cols if 'region' in str(c).lower()), cols[1])
                    
                    # 3) Supermarket 이름: 'Store' 또는 'Plant' 바로 오른쪽 열
                    c_store = next((c for c in cols if 'store' in str(c).lower() or 'plant' in str(c).lower()), None)
                    c_supermarket = cols[cols.index(c_store) + 1] if c_store and cols.index(c_store) + 1 < len(cols) else cols[3]
                    
                    # 4) Product 이름: 'Article' 또는 'Material' 바로 오른쪽 열
                    c_article = next((c for c in cols if 'article' in str(c).lower() or 'material' in str(c).lower()), None)
                    c_product = cols[cols.index(c_article) + 1] if c_article and cols.index(c_article) + 1 < len(cols) else cols[5]
                    
                    # 5) Quantity (수량): 'Qty', 'Quantity', 'Stock' 이 포함된 열
                    c_qty = next((c for c in cols if any(x in str(c).lower() for x in ['qty', 'quantity', 'stock'])), cols[-1])
                    
                    # 필요한 열만 추출
                    df = df[[c_unit, c_reg, c_supermarket, c_product, c_qty]].copy()
                    df.columns = ['unit', 'region', 'supermarket', 'product', 'qty']
                    
                    # 수량을 가장 먼저 안전한 숫자로 변환 (제품 ID가 수량으로 잡히는 버그 방지)
                    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(float)
                    
                    # 문자로 변환 및 빈칸 처리
                    for col in ['unit', 'region', 'supermarket', 'product']:
                        df[col] = df[col].fillna('Khác').astype(str)
                        df.loc[df[col].str.lower() == 'nan', col] = 'Khác'
                        df.loc[df[col] == '', col] = 'Khác'
                        
                    # 유효한 지역만 필터링 (북, 중, 남)
                    valid_mask = df['region'].str.lower().str.contains('bắc|trung|nam', na=False, regex=True)
                    df = df[valid_mask].copy()
                    
                    df['type'] = data_type
                    return df

                # 판매/재고 시트 각각 분석
                df_sales = process_sheet(sales_sheet, 'sales')
                df_inv = process_sheet(inv_sheet, 'inventory')

                # 병합 및 피벗 테이블 생성
                df_combined = pd.concat([df_sales, df_inv], ignore_index=True)
                
                if not df_combined.empty:
                    df_grouped = df_combined.pivot_table(
                        index=['unit', 'region', 'supermarket', 'product'], 
                        columns='type', values='qty', aggfunc='sum', fill_value=0
                    ).reset_index()

                    if 'sales' not in df_grouped.columns: df_grouped['sales'] = 0
                    if 'inventory' not in df_grouped.columns: df_grouped['inventory'] = 0

                    df_grouped['year'] = file_year
                    df_grouped['month'] = file_month
                    all_data.append(df_grouped)
            else:
                st.sidebar.error(f"❌ {uploaded_file.name}: Không tìm thấy sheet Bán/Tồn (판매/재고 시트 오류)")
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi ({uploaded_file.name}): {e}")

if all_data:
    df = pd.concat(all_data, ignore_index=True)
else:
    df = pd.DataFrame(columns=['year', 'month', 'unit', 'region', 'supermarket', 'product', 'sales', 'inventory'])

# --- 메인 화면 ---
st.title("📊 Dữ Liệu Dashboard (Bán hàng & Tồn kho)")

if df.empty:
    st.info("Không có dữ liệu. Vui lòng kéo thả tệp Excel lên từ thanh bên trái.")
else:
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

    filtered_df = df[
        (df['year'].isin(f_year) if f_year else True) &
        (df['month'].isin(f_month) if f_month else True) &
        (df['unit'].isin(f_unit) if f_unit else True) &
        (df['region'].isin(f_region) if f_region else True) &
        (df['supermarket'].isin(f_supermarket) if f_supermarket else True) &
        (df['product'].isin(f_product) if f_product else True)
    ]

    total_sales = filtered_df['sales'].sum()
    total_inv = filtered_df['inventory'].sum()
    stock_months = (total_inv / total_sales) if total_sales > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng số mục (필터링 항목 수)", f"{len(filtered_df):,} mục")
    col2.metric("Tổng Bán (총 판매)", f"{total_sales:,.0f}")
    col3.metric("Tổng Tồn kho (총 재고)", f"{total_inv:,.0f}", f"{stock_months:.1f} tháng tồn")

    st.subheader("Bảng tổng hợp (필터링된 데이터 합계)")
    summary_df = pd.DataFrame({
        'Phân loại (구분)': ['Tổng cộng (합계)'],
        'Tổng Bán (총 판매)': [f"{total_sales:,.0f}"],
        'Tổng Tồn kho (총 재고)': [f"{total_inv:,.0f}"],
        'Tháng tồn kho (재고개월수)': [f"{stock_months:.1f}"]
    })
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("Biểu đồ xu hướng (월별 추이)")
    if not filtered_df.empty:
        trend_df = filtered_df.groupby(['year', 'month'])[['sales', 'inventory']].sum().reset_index()
        trend_df = trend_df.sort_values(by=['year', 'month'])
        trend_df['label'] = trend_df.apply(lambda x: f"T{int(x['month'])}/{int(x['year'])}", axis=1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=trend_df['label'], y=trend_df['inventory'], name='Tồn kho (재고)', marker_color='#f59e0b'))
        fig.add_trace(go.Scatter(x=trend_df['label'], y=trend_df['sales'], name='Bán hàng (판매)', mode='lines+markers', line=dict(color='#10b981', width=3)))
        fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
