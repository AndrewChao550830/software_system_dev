import streamlit as st
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# -------------------------- 頁面初始化設定 --------------------------
st.set_page_config(
    page_title="產品標註審核儀表板",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------- 範例產品資料 --------------------------
def load_sample_product_data() -> List[Dict[str, Any]]:
    """載入範例產品資料"""
    sample_data = [
        {
            "product_id": "PROD001",
            "name": "智慧型手機 X1",
            "category": "電子產品",
            "price": 29990,
            "image_url": "https://via.placeholder.com/300x200/0066CC/FFFFFF?text=手機+X1",
            "label_status": "pending",
            "annotations": {
                "brand": "TechCorp",
                "model": "X1",
                "color": "深空灰",
                "storage": "128GB"
            }
        },
        {
            "product_id": "PROD002",
            "name": "無線耳機 Pro",
            "category": "電子產品",
            "price": 3990,
            "image_url": "https://via.placeholder.com/300x200/00CC66/FFFFFF?text=耳機+Pro",
            "label_status": "approved",
            "annotations": {
                "brand": "SoundMax",
                "model": "Pro",
                "type": "無線",
                "noise_cancelling": True
            }
        },
        {
            "product_id": "PROD003",
            "name": "筆記型電腦 Z15",
            "category": "電子產品",
            "price": 45990,
            "image_url": "https://via.placeholder.com/300x200/CC6600/FFFFFF?text=筆電+Z15",
            "label_status": "pending",
            "annotations": {
                "brand": "ComputePlus",
                "model": "Z15",
                "screen_size": "15.6吋",
                "ram": "16GB"
            }
        },
        {
            "product_id": "PROD004",
            "name": "專業相機 MarkIII",
            "category": "攝影器材",
            "price": 62990,
            "image_url": "https://via.placeholder.com/300x200/6600CC/FFFFFF?text=相機+MarkIII",
            "label_status": "rejected",
            "annotations": {
                "brand": "PhotoPro",
                "model": "MarkIII",
                "megapixels": "45MP",
                "lens_mount": "EF"
            }
        },
        {
            "product_id": "PROD005",
            "name": "智慧手錶 Series5",
            "category": "穿戴裝置",
            "price": 8990,
            "image_url": "https://via.placeholder.com/300x200/CC0066/FFFFFF?text=手錶+Series5",
            "label_status": "pending",
            "annotations": {
                "brand": "WearTech",
                "model": "Series5",
                "features": ["心率監測", "GPS", "防水"]
            }
        },
        {
            "product_id": "PROD006",
            "name": "4K超高解析度電視",
            "category": "家庭娛樂",
            "price": 35990,
            "image_url": "https://via.placeholder.com/300x200/66CC00/FFFFFF?text=4K+電視",
            "label_status": "approved",
            "annotations": {
                "brand": "ViewMaster",
                "size": "55吋",
                "resolution": "4K UHD",
                "hdr": True
            }
        },
        {
            "product_id": "PROD007",
            "name": "遊戲主機 Warrior",
            "category": "電子產品",
            "price": 12990,
            "image_url": "https://via.placeholder.com/300x200/006699/FFFFFF?text=主機+Warrior",
            "label_status": "pending",
            "annotations": {
                "brand": "GameBox",
                "model": "Warrior",
                "storage": "1TB SSD",
                "ram": "16GB"
            }
        },
        {
            "product_id": "PROD008",
            "name": "專業麥克風 Studio",
            "category": "錄音器材",
            "price": 5990,
            "image_url": "https://via.placeholder.com/300x200/9900CC/FFFFFF?text=麥克風+Studio",
            "label_status": "approved",
            "annotations": {
                "brand": "AudioPro",
                "model": "Studio",
                "type": "電容式",
                "polar_pattern": "心形"
            }
        }
    ]
    return sample_data

# -------------------------- 狀態管理 --------------------------
if "products" not in st.session_state:
    st.session_state.products = load_sample_product_data()

if "selected_products" not in st.session_state:
    st.session_state.selected_products = set()

if "filter_category" not in st.session_state:
    st.session_state.filter_category = "所有類別"

if "filter_price_min" not in st.session_state:
    st.session_state.filter_price_min = 0

if "filter_price_max" not in st.session_state:
    st.session_state.filter_price_max = 100000

if "show_annotations" not in st.session_state:
    st.session_state.show_annotations = {}

# -------------------------- 輔助函數 --------------------------
def get_unique_categories() -> List[str]:
    """取得所有不重複的類別"""
    categories = {"所有類別"}
    for product in st.session_state.products:
        categories.add(product["category"])
    return sorted(list(categories))

def filter_products() -> List[Dict[str, Any]]:
    """根據過濾條件過濾產品"""
    filtered = []
    for product in st.session_state.products:
        # 類別過濾
        if st.session_state.filter_category != "所有類別" and product["category"] != st.session_state.filter_category:
            continue

        # 價格過濾
        if product["price"] < st.session_state.filter_price_min or product["price"] > st.session_state.filter_price_max:
            continue

        filtered.append(product)
    return filtered

def toggle_product_selection(product_id: str):
    """切換產品選取狀態"""
    if product_id in st.session_state.selected_products:
        st.session_state.selected_products.remove(product_id)
    else:
        st.session_state.selected_products.add(product_id)

def select_all_products(products: List[Dict[str, Any]]):
    """選取所有顯示的產品"""
    st.session_state.selected_products = {p["product_id"] for p in products}

def clear_selection():
    """清除所有選取"""
    st.session_state.selected_products.clear()

def approve_selected_labels():
    """批准選取產品的標註"""
    for product_id in st.session_state.selected_products:
        for product in st.session_state.products:
            if product["product_id"] == product_id:
                product["label_status"] = "approved"
                break
    st.success(f"已批准 {len(st.session_state.selected_products)} 件產品的標註")
    clear_selection()

def reject_selected_labels():
    """拒絕選取產品的標註"""
    for product_id in st.session_state.selected_products:
        for product in st.session_state.products:
            if product["product_id"] == product_id:
                product["label_status"] = "rejected"
                break
    st.error(f"已拒絕 {len(st.session_state.selected_products)} 件產品的標註")
    clear_selection()

def export_selected_products():
    """匯出選取的產品"""
    if not st.session_state.selected_products:
        st.warning("請先選取要匯出的產品")
        return

    selected_products = []
    for product in st.session_state.products:
        if product["product_id"] in st.session_state.selected_products:
            selected_products.append(product)

    # 轉換為CSV格式
    df = pd.DataFrame(selected_products)
    csv = df.to_csv(index=False, encoding='utf-8-sig')

    st.download_button(
        label="下載匯出檔案 (CSV)",
        data=csv,
        file_name=f"selected_products_{uuid.uuid4().hex[:8]}.csv",
        mime="text/csv"
    )

    st.info(f"準備匯出 {len(selected_products)} 件產品的資料")
    clear_selection()

# -------------------------- 側邊欄 - 過濾器 --------------------------
with st.sidebar:
    st.header("🔍 過濾條件")

    # 類別過濾
    categories = get_unique_categories()
    selected_category = st.selectbox(
        "產品類別",
        options=categories,
        index=categories.index(st.session_state.filter_category) if st.session_state.filter_category in categories else 0,
        key="category_filter"
    )
    if selected_category != st.session_state.filter_category:
        st.session_state.filter_category = selected_category
        st.rerun()

    st.divider()

    # 價格範圍過濾
    st.subheader("價格範圍")
    col1, col2 = st.columns(2)
    with col1:
        price_min = st.number_input(
            "最低價格",
            min_value=0,
            value=st.session_state.filter_price_min,
            step=1000,
            key="price_min"
        )
        if price_min != st.session_state.filter_price_min:
            st.session_state.filter_price_min = price_min
            st.rerun()

    with col2:
        price_max = st.number_input(
            "最高價格",
            min_value=0,
            value=st.session_state.filter_price_max,
            step=1000,
            key="price_max"
        )
        if price_max != st.session_state.filter_price_max:
            st.session_state.filter_price_max = price_max
            st.rerun()

    # 價格範圍顯示
    st.caption(f"目前價格範圍: ${st.session_state.filter_price_min:,} - ${st.session_state.filter_price_max:,}")

    st.divider()

    # 批量操作說明
    st.subheader("📋 批量操作")
    selected_count = len(st.session_state.selected_products)
    if selected_count > 0:
        st.info(f"已選取 {selected_count} 件產品")
        if st.button("清除選取", type="secondary"):
            clear_selection()
            st.rerun()
    else:
        st.caption("目前沒有選取任何產品")

# -------------------------- 主頁面 --------------------------
st.title("🏷️ 產品標註審核儀表板")
st.caption("使用此儀表板來審核和管理產品標註資料")

# 顯示統計資訊
filtered_products = filter_products()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("總產品數", len(st.session_state.products))
with col2:
    st.metric("過濾後顯示", len(filtered_products))
with col3:
    approved_count = sum(1 for p in st.session_state.products if p["label_status"] == "approved")
    st.metric("已批准", approved_count)
with col4:
    pending_count = sum(1 for p in st.session_state.products if p["label_status"] == "pending")
    st.metric("待審核", pending_count)

st.divider()

# 批量操作按鈕
if st.session_state.selected_products:
    st.subheader("🚀 批量操作")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("✅ 批准選取項目", type="primary", use_container_width=True):
            approve_selected_labels()
            st.rerun()
    with col2:
        if st.button("❌ 拒絕選取項目", type="secondary", use_container_width=True):
            reject_selected_labels()
            st.rerun()
    with col3:
        if st.button("📤 匯出選取項目", type="secondary", use_container_width=True):
            export_selected_products()
            st.rerun()
    with col4:
        if st.button("☑️ 選取所有顯示項目", type="secondary", use_container_width=True):
            select_all_products(filtered_products)
            st.rerun()

st.divider()

# 產品顯示區域
st.subheader("📦 產品列表")

if not filtered_products:
    st.info("目前沒有符合過濾條件的產品")
else:
    # 三欄佈局
    cols = st.columns(3)

    for idx, product in enumerate(filtered_products):
        col_idx = idx % 3
        with cols[col_idx]:
            # 產品卡片
            with st.container(border=True):
                # 選取核取方塊
                is_selected = product["product_id"] in st.session_state.selected_products
                if st.checkbox("", value=is_selected, key=f"select_{product['product_id']}", label_visibility="hidden"):
                    if not is_selected:
                        toggle_product_selection(product["product_id"])
                else:
                    if is_selected:
                        toggle_product_selection(product["product_id"])

                # 產品圖片與標註切換
                show_ann = st.session_state.show_annotations.get(product["product_id"], False)
                if st.button(
                    f"{'👁️‍🗨️ 顯示標註' if not show_ann else '👁️ 隱藏標註'}",
                    key=f"toggle_ann_{product['product_id']}",
                    use_container_width=True
                ):
                    st.session_state.show_annotations[product["product_id"]] = not show_ann
                    st.rerun()

                # 顯示圖片
                st.image(product["image_url"], use_column_width=True)

                # 產品資訊
                st.markdown(f"**{product['name']}**")
                st.caption(f"類別: {product['category']} | 价格: ${product['price']:,}")

                # 標註狀態標籤
                status_colors = {
                    "pending": "orange",
                    "approved": "green",
                    "rejected": "red"
                }
                status_label = {
                    "pending": "待審核",
                    "approved": "已批准",
                    "rejected": "已拒絕"
                }

                status_color = status_colors.get(product["label_status"], "gray")
                status_text = status_label.get(product["label_status"], product["label_status"])

                st.markdown(
                    f"<span style='background-color: {status_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;'>{status_text}</span>",
                    unsafe_allow_html=True
                )

                # 顯示標註（如果開啟）
                if st.session_state.show_annotations.get(product["product_id"], False):
                    with st.expander("🔍 查看標註詳情", expanded=True):
                        for key, value in product["annotations"].items():
                            if isinstance(value, list):
                                value = ", ".join(str(v) for v in value)
                            st.text(f"{key}: {value}")

                st.divider()

# -------------------------- 頁腳 --------------------------
st.divider()
st.caption("產品標註審核儀表板 v1.0 | 最後更新: 2026-09-06")