import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import re

# --- 기본 설정 ---
st.set_page_config(page_title="Dữ Liệu Dashboard", layout="wide")

# --- 데이터베이스 초기화 (SQLite) ---
conn = sqlite3.connect('dashboard_data.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS records (
        year INTEGER, month INTEGER, unit TEXT, region TEXT, 
        supermarket TEXT, product TEXT, sales REAL, inventory REAL,
        UNIQUE(year, month, unit, region, supermarket, product)
    )
''')
conn.commit()

# --- 사이드바: 데이터 업로드 (멀티 파일) ---
st.sidebar.title("☁️ Tải lên dữ liệu")
st.sidebar.caption("Bạn có thể kéo thả nhiều tệp cùng lúc (여러 파일을 한 번에 드래그하세요)")

# 파일명에서 날짜를 못 찾을 경우 사용할 기본값
upload_year = st.sidebar.selectbox("Năm mặc định (기본 연도)", [2023, 2024, 2025, 2026, 2027], index=2)
upload_month = st.sidebar.selectbox("Tháng mặc định (기본 월)", list(range(1, 13)), index=0)

# accept_multiple_files=True 로 여러 파일 동시 업로드 허용
uploaded_files = st.sidebar.file_uploader("Chọn tệp Excel (Kéo thả nhiều tệp)", type=['xlsx', 'xls'], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        try:
            # 1. 파일명에서 연도/월 자동 추출 시도 (예: "tháng 01.2025")
            match = re.search(r'tháng\s*(\d{1,2})\.?(\d{4})', uploaded_file.name.lower())
            if match:
                file_month = int(match.group(1))
                file_year = int(match.group(2))
            else:
                file_month = upload_month
                file_year = upload_year

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

                # 병합 및 피벗
                df_combined = pd.concat([df_sales, df_inv]).fillna('Khác')
                df_grouped = df_combined.pivot_table(
                    index=['unit', 'region', 'supermarket', 'product'], 
                    columns='type', values='qty', aggfunc='sum', fill_value=0
                ).reset_index()

                if 'sales' not in df_grouped.columns: df_grouped['sales'] = 0
                if 'inventory' not in df_grouped.columns: df_grouped['inventory'] = 0

                # DB에 저장
                for _, row in df_grouped.iterrows():
                    c.execute('''
                        INSERT OR REPLACE INTO records 
                        (year, month, unit, region, supermarket, product, sales, inventory)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (file_year, file_month, str(row['unit']), str(row['region']), 
                          str(row['supermarket']), str(row['product']), float(row['sales']), float(row['inventory'])))
                conn.commit()
                st.sidebar.success(f"✅ {uploaded_file.name} (T{file_month}/{file_year}) 저장 완료")
            else:
                st.sidebar.error(f"❌ {uploaded_file.name}: Không tìm thấy sheet Bán/Tồn.")
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi ({uploaded_file.name}): {e}")

# --- DB에서 전체 데이터 불러오기 ---
df = pd.read_sql_query("SELECT * FROM records", conn)

# --- 메인 화면 ---
st.title("📊 Dữ Liệu Dashboard (Bán hàng & Tồn kho)")

if df.empty:
    st.info("Không có dữ liệu. Vui lòng kéo thả tệp Excel lên từ thanh bên trái.")
else:
    # --- 사이드바: 필터 ---
    st.sidebar.markdown("---")
    st.sidebar.title("🔍 Bộ lọc (필터)")
    
    def multiselect_filter(label, col_name):
        options = sorted(df[col_name].unique())
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
        (df['year'].isin(f_year)) & (df['month'].isin(f_month)) &
        (df['unit'].isin(f_unit)) & (df['region'].isin(f_region)) &
        (df['supermarket'].isin(f_supermarket)) & (df['product'].isin(f_product))
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
    
    # 1줄짜리 요약 데이터프레임 생성
    summary_data = {
        'Phân loại (구분)': ['Tổng cộng (합계)'],
        'Tổng Bán (총 판매)': [f"{total_sales:,.0f}"],
        'Tổng Tồn kho (총 재고)': [f"{total_inv:,.0f}"],
        'Tháng tồn kho (재고개월수)': [f"{stock_months:.1f}"]
    }
    summary_df = pd.DataFrame(summary_data)
    
    # 요약 표 출력
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # --- 그래프 ---
    st.subheader("Biểu đồ xu hướng (월별 추이)")
    if not filtered_df.empty:
        trend_df = filtered_df.groupby(['year', 'month'])[['sales', 'inventory']].sum().reset_index()
        trend_df['label'] = trend_df.apply(lambda x: f"T{int(x['month'])}/{int(x['year'])}", axis=1)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=trend_df['label'], y=trend_df['inventory'], name='Tồn kho (재고)', marker_color='#f59e0b'))
        fig.add_trace(go.Scatter(x=trend_df['label'], y=trend_df['sales'], name='Bán hàng (판매)', mode='lines+markers', line=dict(color='#10b981', width=3)))
        
        fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
