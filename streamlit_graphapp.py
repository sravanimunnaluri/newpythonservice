import sys
if getattr(sys, 'frozen', False):
    import importlib.metadata
importlib.metadata.distribution = lambda name: type('dummy', (), {'version':'0'})()
import re
import streamlit as st
from etd_new import graph 

st.set_page_config(page_title="Dispatch Readiness Workflow", layout="wide")

# Page title
st.title("Dispatch Readiness Workflow")

# --- Input fields ---

customer_name = st.text_input("Customer Name", max_chars=50)
finished_good = st.text_input("Finished Good", max_chars=100)
quantity = st.number_input("Quantity (KGs)", min_value=1, step=1)

# --- Validators ---

def validate_customer_name(name):
    return bool(re.match(r"^[A-Za-z\s]+$", name.strip()))

def validate_finished_good(fg):
    return bool(re.match(r"^[A-Za-z0-9\s]+$", fg.strip()))

def validate_quantity(qty: int):
    return isinstance(qty, int) and qty > 0
def _df_or_empty(data: list):
    import pandas as pd
    return pd.DataFrame(data) if data else pd.DataFrame()

def _auto_height(df, base: int = 120, row_height: int = 28, max_height: int = 500):
    if df is None or df.empty:
        return base
    rows = len(df)
    return min(max_height, base + rows * row_height)

def render_streamlit_report(state: dict):
    import pandas as pd

    customer = state["input_json"].get("customer_name", "")
    fg = state["input_json"].get("finished_good", "")
    qty = state["input_json"].get("quantity", "")
    fg_status = state.get("fg_is_ready", False)
    dispatch_date = state.get("dispatch_date", "N/A")

    st.markdown("**BLEND COLOURS**")
    st.subheader("Dispatch Readiness Report")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Finished Good", fg)
    with col2:
        st.metric("Quantity (KGs)", qty)
    with col3:
        st.metric("Status", "Ready" if fg_status else "Not Ready")
    st.caption(f"Dispatch Date: {dispatch_date}")

    tabs = st.tabs([
        "BOM",
        "Available RM",
        "Unavailable RM",
        "Alternate RM's",
        "Alternate RM's Stock Status",
        "Suppliers",
        "All Machines",
        "Final Machine",
    ])

    bom = _df_or_empty(state.get("bom_result", []))
    avail = _df_or_empty(state.get("rm_availability", []))
    miss = _df_or_empty(state.get("rm_missing", []))
    alts = _df_or_empty(state.get("alternatives", []))
    alt_stock = _df_or_empty(state.get("altrm_stockavailability_table", []))
    suppliers = _df_or_empty(state.get("rm_supplier_name", []))
    all_m = _df_or_empty(state.get("all_machines_for_Fg", []))
    final_m = _df_or_empty(state.get("final_machine", []))

    # Column selections per requirements
    def _select_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        present = [c for c in cols if c in df.columns]
        return df[present] if present else df

    bom_cols = [
        "BillOfMaterial",
        "Product",
        "InputProduct",
        "QtyRequired",
        "Balance",
        "AfterConsumption",
    ]
    alt_cols = [
        "ActualBOMInputProduct",
        "UsedProduct",
        "notimesused",
        "AlternateProductBalance",
    ]
    alt_stock_cols = [
        "ActualBOMInputProduct",
        "UsedProduct",
        "notimesused",
        "AlternateProductBalance",
        "stockavailability",
    ]

    bom_v = _select_cols(bom, bom_cols)
    avail_v = _select_cols(avail, bom_cols)
    miss_v = _select_cols(miss, bom_cols)
    alts_v = _select_cols(alts, alt_cols)
    alt_stock_v = _select_cols(alt_stock, alt_stock_cols)
    if alt_stock_v is not None and not alt_stock_v.empty and "stockavailability" in alt_stock_v.columns:
        alt_stock_v = alt_stock_v.rename(columns={"stockavailability": "Availability"})

    # Color-code tab headers when data is empty (subtle grey)
    empty_flags = [
        bom_v is None or bom_v.empty,
        avail_v is None or avail_v.empty,
        miss_v is None or miss_v.empty,
        alts_v is None or alts_v.empty,
        alt_stock_v is None or alt_stock_v.empty,
        suppliers is None or suppliers.empty,
        all_m is None or all_m.empty,
        final_m is None or final_m.empty,
    ]
    style_rules = []
    for idx, is_empty in enumerate(empty_flags, start=1):
        if is_empty:
            style_rules.append(
                f"div[role='tablist'] button:nth-child({idx}) {{ color: #9E9E9E !important; }}"
            )
            style_rules.append(
                f"div[data-baseweb='tab-list'] button:nth-child({idx}) {{ color: #9E9E9E !important; }}"
            )
    if style_rules:
        st.markdown("<style>" + "\n".join(style_rules) + "</style>", unsafe_allow_html=True)

    with tabs[0]:
        st.dataframe(bom_v, use_container_width=True, height=_auto_height(bom_v))
    with tabs[1]:
        if avail_v is None or avail_v.empty:
            st.info("No Available RM's")
        else:
            st.dataframe(avail_v, use_container_width=True, height=_auto_height(avail_v))
    with tabs[2]:
        st.dataframe(miss_v, use_container_width=True, height=_auto_height(miss_v))
    with tabs[3]:
        st.dataframe(alts_v, use_container_width=True, height=_auto_height(alts_v))
    with tabs[4]:
        st.dataframe(alt_stock_v, use_container_width=True, height=_auto_height(alt_stock_v))
    with tabs[5]:
        if suppliers.empty:
            st.info("No suppliers needed or NO suppliers found for the missing raw materials.")
        else:
            st.dataframe(suppliers, use_container_width=True, height=_auto_height(suppliers))
    with tabs[6]:
        if all_m.empty:
            st.info(f"No machine tagged for {fg}")
        else:
            st.dataframe(all_m, use_container_width=True, height=_auto_height(all_m))
    with tabs[7]:
        if final_m.empty:
            st.info(f"No final machine selection for {fg}")
        else:
            st.dataframe(final_m, use_container_width=True, height=_auto_height(final_m))


# --- Show Workflow Graph Button ---
if st.button("Show Workflow Graph"):
    try:
        img_data = graph.get_graph().draw_mermaid_png()
        st.image(img_data, caption="Workflow Graph")
    except Exception as e:
        st.error("Error generating graph.")
        st.exception(e)

# --- Generate Report Button ---
if st.button("Generate Report"):
    try:
        # Validation
        if not validate_customer_name(customer_name):
            st.error("Customer Name must contain only letters and spaces.")
        elif not validate_finished_good(finished_good):
            st.error("Finished Good must be alphanumeric.")
        elif not validate_quantity(quantity):
            st.error("Quantity must be a positive integer.")
        else:
            # Build input JSON
            input_payload = {
                "input_json": {
                    "customer_name": customer_name.strip(),
                    "finished_good": finished_good.strip(),
                    "quantity": int(quantity)
                }
            }

            st.info("Running workflow...")
            result_state = graph.invoke(input_payload)

            if "final_report" in result_state:
                st.subheader("Generated Dispatch Report")
                # --- Download Excel Button ---
                import pandas as pd
                import io
                tables = {
                    "BOM": pd.DataFrame(result_state.get("bom_result", [])),
                    "Available Raw Materials": pd.DataFrame(result_state.get("rm_availability", [])),
                    "Unavailable Raw Materials": pd.DataFrame(result_state.get("rm_missing", [])),
                    "Alternatives for Unavailable RM": pd.DataFrame(result_state.get("alternatives", [])),
                    "Alternatives Stock Availability": pd.DataFrame(result_state.get("altrm_stockavailability_table", [])),
                    "Suppliers for Raw Materials": pd.DataFrame(result_state.get("rm_supplier_name", [])),
                    "All Machines for FG": pd.DataFrame(result_state.get("all_machines_for_Fg", [])),
                    "Final Machine Allotment": pd.DataFrame(result_state.get("final_machine", [])),
                }
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    for name, df in tables.items():
                        if not df.empty:
                            df.to_excel(writer, sheet_name=name, index=False)
                output.seek(0)
                # Use a container to keep the download button and report together
                with st.container():
                    st.download_button(
                        label="Download Full Report",
                        data=output.read(),
                        file_name="dispatch_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    render_streamlit_report(result_state)
            else:
                st.warning("Workflow completed but no report was generated.")
    except Exception as e:
        st.error("Error running workflow.")
        st.exception(e)
