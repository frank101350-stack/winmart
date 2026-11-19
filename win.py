import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re

# --- 기본 설정 ---
st.set_page_config(page_title="Dữ Liệu Dashboard", layout="wide")

# --- 사이드바: 데이터 업로드 (멀티 파일) ---
st.sidebar.title("☁️ Tải lên dữ liệu")
st.sidebar.caption("Bạn có thể kéo thả nhiều tệp cùng lúc (여러 파일을 한 번에 드래그하세요)")

uploaded_files = st.sidebar.file_uploader("Chọn tệp Excel (Kéo thả nhiều tệp)", type=['xlsx', 'xls'], accept_multiple_files=True)

all_data = [] 

if uploaded_files:
    for uploaded_file in uploaded_files:
        try:
            # 1. 파일명에서 연도/월 자동 추출 시도
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
            sales_sheet = next((s for s in xls.sheet_names if 'bán' in s.lower() or '판매' in s.lower()), None)
            inv_sheet = next((s for s in xls.sheet_names if 'tồn' in s.lower() or '재고' in s.lower()), None)

            if sales_sheet and inv_sheet:
                # 판매 데이터
                df_sales = pd.read_excel(uploaded_file, sheet_name=sales_sheet, header=1)
                df_sales = df_sales.iloc[:, [0, 1, 3, 5, 6]].dropna(subset=[df_sales.columns[0]])
                df_sales.columns = ['unit', 'region', 'supermarket', 'product', 'qty']
                df_sales['type'] = 'sales'

                # 재고 데이터
                df_inv = pd.read_excel(uploaded_file, sheet_name=inv_sheet, header=1)
                df_inv = df_inv.iloc[:, [0, 1, 3, 5, 6]].dropna(subset=[df_inv.columns[0]])
                df_inv.columns = ['unit', 'region', 'supermarket', 'product', 'qty']
                df_inv['type'] = 'inventory'

                # 병합 및 피벗 (결측치는 'Khác'으로 채우고 모든 기준열을 문자로 강제 변환)
                df_combined = pd.concat([df_sales, df_inv]).fillna('Khác')
                for col in ['unit', 'region', 'supermarket', 'product']:
                    df_combined[col] = df_combined[col].astype(str)

                df_grouped = df_combined.pivot_table(
                    index=['unit', 'region', 'supermarket', 'product'], 
                    columns='type', values='qty', aggfunc='sum', fill_value=0
                ).reset_index()

                if 'sales' not in df_grouped.columns: df_grouped['sales'] = 0
                if 'inventory' not in df_grouped.columns: df_grouped['inventory'] = 0

                # 연도와 월 정보 추가
                df_grouped['year'] = file_year
                df_grouped['month'] = file_month

                # 리스트에 추가 (성공 메시지 st.sidebar.success 제거)
                all_data.append(df_grouped)
            else:
                st.sidebar.error(f"❌ {uploaded_file.name}: Không tìm thấy sheet Bán/Tồn.")
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
        # TypeError 해결: key=str을 추가하여 숫자와 문자가 섞여 있어도 안전하게 정렬되도록 수정
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
