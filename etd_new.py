from typing import TypedDict, Optional, List, Dict
import pandas as pd
from langgraph.graph import StateGraph
from langchain_core.tools import tool
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage
from typing import TypedDict, List, Dict, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from IPython.display import Image
import pyodbc
import logging
import streamlit as st
db = st.secrets["database"]

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FGState(TypedDict):
    input_json: dict
    fg_sql: Optional[str]
    fg_available_qty: Optional[float]
    fg_is_ready: Optional[bool]
    bom_sql: Optional[str]
    bom_result: Optional[List[Dict]]
    rm_availability: Optional[List[Dict]]
    rm_missing: Optional[List[Dict]]
    rm_missing_flag: Optional[bool]
    alternatives: Optional[Dict[str, List[str]]]
    alternatives_eqlst: Optional[Dict[str, List[str]]]
    alternatives_available_stock: Optional[List[Dict]]
    alternatives_unavailable_stock: Optional[List[Dict]]
    altrm_stockavailability_table: Optional[List[Dict]]
    unavailable_inputs: Optional[bool]
    rm_supplier_name:Optional[List[Dict]]
    available_machines: Optional[List[Dict]]
    all_machines_for_Fg: Optional[List[Dict]]
    final_machine: Optional[List[Dict]]
    machine_flag: Optional[str]
    dispatch_date: Optional[str]
    final_report: Optional[str]


#sql conection
conn = pyodbc.connect(
    f"DRIVER={{{db['DRIVER']}}};SERVER={db['SERVER']};DATABASE={db['DATABASE']};UID={db['UID']};PWD={db['PWD']};TrustServerCertificate=yes;Encrypt=no;Connection Timeout=10;"
)
@tool
def check_fg_inventory(FG: str) -> str:
    """Returns a raw SQL query to check if FG is in stock."""
    return f"SELECT SUM(ISNULL(receivedqty, 0) - ISNULL(issuedqty, 0)) AS StkBalance FROM StockLedger_Table WHERE Product = '{FG}' GROUP BY Product"

@tool
def get_bom_for_FG(FG: str) -> dict:
    """this funciton will retrurn query to check whether it has the FG in inventory"""
    return {"sql_query": f"select * from Master_BillsOfMaterial_Table where product='{FG}'"}

@tool
def new_bom_fetch(FG,qty: str) -> str:
    """this function will fetch BOM along with the balance values in db"""
    
    qrr = f"""select 
    bom.VoucherLineNo Sno
    ,bom.MasterName BillOfMaterial
    ,bom.Product
    ,bom.Unit
    ,bom.InputProduct
    ,bom.InputUnit
    ,bom.InputQuantity
    ,bom.InputQtyCF
    ,bom.InputQtyInBaseUOM
    ,(bom.InputQtyInBaseUOM * {int(qty)}) QtyRequired
    ,bom.Comments PercentOfMaterial
    ,stkbal.Balance
    ,stkbal.Balance - (bom.InputQtyInBaseUOM * {int(qty)}) AfterConsumption
    from 
        Master_BillsOfMaterial_Table bom
            left join (select Product,sum(isnull(receivedqty,0)-isnull(issuedqty,0)) Balance 
                        from StockLedger_Table group by Product) stkbal on stkbal.Product = bom.InputProduct
    where  
        bom.Product  = '{FG}'
    order by
        sno"""
    return qrr

@tool
def sql_executor(sql_query: str) -> str:
    """This function will take a raw SQL query and return the result as JSON."""
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df.to_json(orient='records')
    except Exception as e:
        return f"SQL execution failed: {e}"

# @tool
# def get_alternate_RM(RM: str) -> str:
#     """"this tool has query to fetch the alternative raw material"""
#     return f"SELECT UsedProduct, COUNT(*) as number_of_times_used, SUM(Quantity) as QtyUsed, (SUM(Quantity) / (SELECT SUM(Quantity) FROM AlternateProductsUsedInProduction WHERE ActualBOMInputProduct = '{RM}')) * 100 as Weightage_by_QtyUsed FROM AlternateProductsUsedInProduction WHERE ActualBOMInputProduct = '{RM}' GROUP BY UsedProduct ORDER BY number_of_times_used DESC, QtyUsed DESC"

@tool
def get_alternative_rm_from_eqvList(RM: str) ->str:
    """this will fetch the Alternate RM from the lIst"""
    alternative_rm_list = f"""
    select * from RMEquivalantDetails_Table where eqlist in
    (select eqlist from RMEquivalantDetails_Table where rm = '{RM}')
    and rm<>'{RM}'
    """
    return alternative_rm_list

@tool
def new_alternate_RM_fetch(FG: str) -> str:
    """this will fetch all the alternatives for all the RM's in the BOM"""
    q2_get_alternative = f"""
    SELECT
        a.ActualBOMInputProduct,
        a.UsedProduct,
        COUNT(1) AS notimesused,
        SUM(a.Quantity) AS QtyUsed,
        SUM(a.Quantity) * 1.0 / COUNT(1) AS AvgQty,
        (SUM(a.Quantity) * 100.0) /
        (
            SELECT SUM(sa.Quantity)
            FROM AlternateProductsUsedInProduction sa
            WHERE sa.ActualBOMInputProduct = a.ActualBOMInputProduct
        ) AS Weightage,
        stkbal.Balance AS AlternateProductBalance
    FROM AlternateProductsUsedInProduction a
    LEFT JOIN (
        SELECT
            Product,
            SUM(ISNULL(receivedqty,0) - ISNULL(issuedqty,0)) AS Balance
        FROM StockLedger_Table
        GROUP BY Product
    ) stkbal
        ON stkbal.Product = a.UsedProduct
    WHERE a.ActualBOMInputProduct IN (
        SELECT bom.InputProduct
        FROM Master_BillsOfMaterial_Table bom
        WHERE bom.Product = '{FG}'
    )
    GROUP BY
        a.ActualBOMInputProduct,
        a.UsedProduct,
        stkbal.Balance
    ORDER BY
        a.ActualBOMInputProduct,
        Weightage DESC,
        notimesused DESC,
        QtyUsed DESC;
    """
    return q2_get_alternative

@tool
def sql_supplier(fg: str) -> str:
    """this will fetch the query for suppliers"""
    qr = f"""
        SELECT DISTINCT
            tib.Product,
            tht.Account AS Vendor
        FROM Transaction_ItemBody_Table tib
        JOIN Transaction_Header_Table tht
            ON tht.VoucherSeries = tib.VoucherSeries
            AND tht.VoucherNo = tib.VoucherNo
        WHERE
            (tib.VoucherSeries LIKE 'MR%' OR tib.VoucherSeries LIKE 'PI%')
            AND tib.Product IN (
                SELECT
                    bom.InputProduct
                FROM Master_BillsOfMaterial_Table bom
                LEFT JOIN (
                    SELECT
                        Product,
                        SUM(ISNULL(receivedqty,0) - ISNULL(issuedqty,0)) AS Balance
                    FROM StockLedger_Table
                    GROUP BY Product
                ) stkbal
                    ON stkbal.Product = bom.InputProduct
                WHERE
                    bom.Product = '{fg}'
                    
            )
        ORDER BY tib.Product;"""
    return qr

@tool
def fetch_rm_supplier(state: FGState) -> FGState:
    """this will fetch the query for suppliers"""
    import pandas as pd
    logger.info(f"DEBUG inside suppliers")
    rm_missing = state["rm_missing"]
    fg = state["input_json"]["finished_good"]
    qty = state["input_json"]["quantity"]

    # Run the supplier query with FG and quantity
    sql = sql_supplier.invoke({
        "fg": fg
    })

    logger.info(f"DEBUG after sql - : {sql}")

    # Load query result into DataFrame
    df_suppliers = pd.read_sql(sql, conn)

    if not rm_missing:
        # Nothing missing, nothing to fetch
        state["rm_supplier_name"] = []
        return state

    # Extract the missing InputProducts
    missing_inputs = [rm["InputProduct"] for rm in rm_missing]
    logger.info(f"DEBUG missing_inputs sql - : {missing_inputs}")


    # Filter suppliers to only those supplying missing RMs
    df_filtered = df_suppliers[
        df_suppliers["Product"].isin(missing_inputs)
    ]

    logger.info(f"DEBUG get_alterrm_stock_availability - : {df_filtered}")

    # Convert to list of dicts and store in state
    state["rm_supplier_name"] = df_filtered.to_dict(orient="records")

    return state


# @tool
# def get_machine_details_for_fg(FG: FGState) -> FGState:
#     """this function will fetch the machine allotment for the FG"""
#     qr = f""" 

#     """




#nodes and conditions
import json
def log_state(state, node_name):
    try:
        logger.info(f"[{node_name}] STATE: {json.dumps(state, default=str, indent=2)}")
    except Exception as e:
        logger.error(f"[{node_name}] Failed to log state: {e}")

def check_fg_stock(state: FGState) -> FGState:
    logger.info("[check_fg_stock] Start")
    fg = state["input_json"]["finished_good"]
    fg_sql = check_fg_inventory.invoke({"FG": fg})
    logger.info(f"[check_fg_stock] fg_sql: {fg_sql}")
    state["fg_sql"] = fg_sql
    result = sql_executor.invoke({"sql_query": fg_sql})
    logger.info(f"[check_fg_stock] SQL result: {result}")
    try:
        qty = float(eval(result)[0]["StkBalance"])
        state["fg_available_qty"] = qty
        req = state["input_json"]["quantity"]
        state["fg_is_ready"] = float(qty) >= int(req)
        logger.info(f"[check_fg_stock] qty: {qty}, req: {req}, fg_is_ready: {state['fg_is_ready']}")
    except:
        state["fg_available_qty"] = 0.0
    #log_state(state, "check_fg_stock")
    return state

#conditional function to check the fg quantity
def check_dispatch_ready(state: FGState) -> str:
    logger.info("[check_dispatch_ready] Start")
    logger.info(f"[check_dispatch_ready] fg_is_ready: {state.get('fg_is_ready')}")
    #log_state(state, "check_dispatch_ready")
    return "ready" if state["fg_is_ready"] else "not_ready"

def get_bom(state: FGState) -> FGState:
    logger.info("[get_bom] Start")
    fg = state["input_json"]["finished_good"]
    qty = state["input_json"]["quantity"]
    # Tool expects qty as string; ensure correct type
    bom_query = new_bom_fetch.invoke({"FG": fg, "qty": str(qty)})
    logger.info(f"[get_bom] bom_query: {bom_query}")
    sql = bom_query
    state["bom_sql"] = sql
    df_bom = pd.read_sql(sql, conn)
    lst_dict = df_bom.to_dict(orient="records")
    state["bom_result"] = lst_dict
    #log_state(state, "get_bom")
    return state

def get_rm_availablity_status(state: FGState) -> FGState:
    logger.info("[get_rm_availablity_status] Start")
    df = pd.DataFrame(state["bom_result"])
    df_missing = df[df["AfterConsumption"] < 0]
    rm_missing = df_missing.to_dict(orient="records")

    df_available = df[df["AfterConsumption"] >= 0]
    rm_available = df_available.to_dict(orient="records")

    # Save missing RMs in state
    state["rm_missing"] = rm_missing
    state["rm_missing_flag"] = True if rm_missing else False
    state["rm_availability"] = rm_available

    logger.info(f"[get_rm_availablity_status] rm_missing: {rm_missing}")
    logger.info(f"[get_rm_availablity_status] rm_available: {rm_available}")
    #log_state(state, "get_rm_availablity_status")

    return state


def check_rm_stock(state: FGState) -> str:

    logger.info("[check_rm_stock] Start")
    logger.info(f"[check_rm_stock] rm_missing_flag: {state.get('rm_missing_flag')}")
    #log_state(state, "check_rm_stock")
    
    if state['rm_missing_flag']:
        return "missing_rm"
    else:
        return "sufficient_rm"
    

def fetch_alternatives(state: FGState) -> FGState:
    logger.info("[fetch_alternatives] Start")
    rm_missing = state["rm_missing"]
    
    fg = state["input_json"]["finished_good"]
    sql = new_alternate_RM_fetch.invoke({"FG": fg})
    logger.info(f"[fetch_alternatives] sql: {sql}")
    df_alternate_bom = pd.read_sql(sql, conn) #this will take fg as input and return the alternatives for all the bom RM
    df_final = df_alternate_bom[
        
        (df_alternate_bom["Weightage"] > 4) &
        (df_alternate_bom["ActualBOMInputProduct"] != df_alternate_bom["UsedProduct"])
    ]
    missing_inputs = [rm_col["InputProduct"] for rm_col in rm_missing]
    df_final1 = df_final[df_final["ActualBOMInputProduct"].isin(missing_inputs)]



    # state["alternatives"] = df_final1.to_dict(orient="records") #this will have the required alternatives for out of stock rm's
    # logger.info(f"[fetch_alternatives] alternatives: {state['alternatives']}")


    #eqv list code 
    lst_eq_alternatives = []
    
    for rm_m in rm_missing:
        rm_mis = rm_m["InputProduct"]
        logger.info(f"[fetch_alternatives] rm_mis: {rm_mis}")
        lst_sql = get_alternative_rm_from_eqvList.invoke({"RM": rm_mis})
        logger.info(f"[fetch_alternatives]  sql: {lst_sql}")
        df_alternate_eq = pd.read_sql(lst_sql, conn)
        eq_list = df_alternate_eq.to_dict(orient="records")
        logger.info(f"[fetch_alternatives] eq_list: {eq_list}")
        # Add ActualBOMInputProduct to each dict
        for item in eq_list:
            item["ActualBOMInputProduct"] = rm_mis
        lst_eq_alternatives.extend(eq_list)
    logger.info(f"[fetch_alternatives] lst_eq_alternatives: {lst_eq_alternatives}")

    # Always define df_eq after the loop
    if lst_eq_alternatives:
        df_eq = pd.DataFrame(lst_eq_alternatives)
        # Rename 'rm' to 'RM' if present
        if 'rm' in df_eq.columns:
            df_eq = df_eq.rename(columns={'rm': 'RM'})
        df_intersection = pd.merge(df_final1, df_eq, left_on=['UsedProduct'], right_on=['RM'], how='inner')
    else:
        # Create an empty DataFrame with at least the 'RM' column for safe merging
        df_eq = pd.DataFrame(columns=['RM'])
        df_intersection = df_final1.copy()
    # Rename ActualBOMInputProduct_x to ActualBOMInputProduct if present
    if 'ActualBOMInputProduct_x' in df_intersection.columns:
        df_intersection = df_intersection.rename(columns={'ActualBOMInputProduct_x': 'ActualBOMInputProduct'})

    
    state["alternatives_eqlst"] = lst_eq_alternatives


    state["alternatives"] = df_intersection.to_dict(orient="records") #this will have the required alternatives for out of stock rm's
    logger.info(f"[fetch_alternatives] alternatives: {state['alternatives']}")

    logger.info(f"DEBUG fetch_alternatives - alternatives_eqlst: {state['alternatives_eqlst']}")
    #log_state(state, "fetch_alternatives")

    return state


#condtional check for alter rm
def get_alterrm_stock_availability(state: FGState) -> FGState:
    logger.info("[get_alterrm_stock_availability] Start")
    rm_missing = state["rm_missing"]  # list of dicts with InputProduct and QtyRequired
    alternatives = state["alternatives"]  # already filtered list of dicts

    if not alternatives or not rm_missing:
        state["alternatives_available_stock"] = []
        state["alternatives_unavailable_stock"] = rm_missing
        state["unavailable_inputs"] = True
        logger.info("[get_alterrm_stock_availability] No alternatives or rm_missing")
        #log_state(state, "get_alterrm_stock_availability")
        return state

    # Convert to DataFrames
    df_alts = pd.DataFrame(alternatives)
    df_missing = pd.DataFrame(rm_missing).rename(columns={"InputProduct": "ActualBOMInputProduct"})

    # Step 1: Get top 3 alternatives per ActualBOMInputProduct
    df_top3 = df_alts.sort_values(
        ["ActualBOMInputProduct", "Weightage"],
        ascending=[True, False]
    ).groupby("ActualBOMInputProduct").head(3)

    # Step 2: Merge with QtyRequired from rm_missing
    df_merged = pd.merge(
        df_top3,
        df_missing[["ActualBOMInputProduct", "QtyRequired"]],
        on="ActualBOMInputProduct",
        how="inner"
    )

    # Step 3: Filter where alternative has enough stock
    df_available = df_merged[
        df_merged["AlternateProductBalance"] >= df_merged["QtyRequired"]
    ]

    #FOR ALTERNATIVE RM STOCK AVAILABILITY TABLE >>>>>>
    # Create df_altrm_stock_status with stockavailability column
    df_altrm_stock_status = df_merged.copy()
    # Set of tuples for fast lookup (ActualBOMInputProduct, UsedProduct) in df_available
    available_set = set(zip(df_available["ActualBOMInputProduct"], df_available["UsedProduct"]))
    def get_stock_status(row):
        key = (row["ActualBOMInputProduct"], row["UsedProduct"])
        return "available" if key in available_set else "not available"
    df_altrm_stock_status["stockavailability"] = df_altrm_stock_status.apply(get_stock_status, axis=1)

    state["altrm_stockavailability_table"] = df_altrm_stock_status.to_dict(orient="records")
    #>>>>>>>>>>>>>>

    # Step 4: Identify which ActualBOMInputProducts still have no alternatives
    available_inputs = set(df_available["ActualBOMInputProduct"])
    all_missing_inputs = set(df_missing["ActualBOMInputProduct"])
    unavailable_inputs = all_missing_inputs - available_inputs
    state["unavailable_inputs"] = True if unavailable_inputs else False

    # Step 5: Save to state
    state["alternatives_available_stock"] = df_available.to_dict(orient="records")

    df_unavailable = df_missing[
        df_missing["ActualBOMInputProduct"].isin(unavailable_inputs)
    ]
    state["alternatives_unavailable_stock"] = df_unavailable.to_dict(orient="records")

    logger.info(f"[get_alterrm_stock_availability] alternatives_available_stock: {state['alternatives_available_stock']}")
    logger.info(f"[get_alterrm_stock_availability] unavailable_inputs: {state['unavailable_inputs']}")
    logger.info(f"[get_alterrm_stock_availability] alternatives_unavailable_stock: {state['alternatives_unavailable_stock']}")
    #log_state(state, "get_alterrm_stock_availability")

    return state

def check_alterrm_stock(state: FGState) -> str:
    logger.info("[check_alterrm_stock] Start")
    logger.info(f"[check_alterrm_stock] unavailable_inputs: {state.get('unavailable_inputs')}")
    #log_state(state, "check_alterrm_stock")

    # Final condition check
    return "altrm_available" if not state['unavailable_inputs'] else "altrm_unavailable"

def fetch_rm_supplier(state: FGState) -> FGState:
    logger.info("[fetch_rm_supplier] Start")
    import pandas as pd
    logger.info(f"DEBUG inside suppliers")
    rm_missing = state["rm_missing"]
    fg = state["input_json"]["finished_good"]
    qty = state["input_json"]["quantity"]

    # Run the supplier query with FG and quantity
    sql = sql_supplier.invoke({
        "fg": fg
    })
    logger.info(f"[fetch_rm_supplier] sql: {sql}")


    # Load query result into DataFrame
    df_suppliers = pd.read_sql(sql, conn)

    if not rm_missing:
        # Nothing missing, nothing to fetch
        state["rm_supplier_name"] = []
        return state
    

    # Extract the missing InputProducts
    missing_inputs = [rm["InputProduct"] for rm in rm_missing]
    logger.info(f"[fetch_rm_supplier] missing_inputs: {missing_inputs}")


    # Filter suppliers to only those supplying missing RMs
    df_filtered = df_suppliers[
        df_suppliers["Product"].isin(missing_inputs)
    ]

    logger.info(f"DEBUG get_alterrm_stock_availability - : {df_filtered}")

    # Convert to list of dicts and store in state
    state["rm_supplier_name"] = df_filtered.to_dict(orient="records")
    logger.info(f"[fetch_rm_supplier] rm_supplier_name: {state['rm_supplier_name']}")

    return state

def machine_allotment(state: FGState) -> FGState:
    import math
    import pytz
    from datetime import datetime, timedelta

    logger.info("[fetch_rm_supplier] Start")

    FG = state["input_json"]["finished_good"]
    qty = float(state["input_json"]["quantity"])  # requested quantity
    fg_available_qty_now = float(state["fg_available_qty"])  # current stock

    # Quantity that still needs to be produced (never negative)
    remaining_qty = max(0.0, qty - fg_available_qty_now)
    logger.info(f"[machine_allotment] qty={qty}, fg_available_qty_now={fg_available_qty_now}, remaining_qty={remaining_qty}")

    machine_details = f"select * from ProductWiseMachinesUsedByHistory where product = '{FG}';"

    logger.info(f"[fetch_rm_supplier] machine_details: {machine_details}")

    df_machines = pd.read_sql(machine_details, conn)

    state["all_machines_for_Fg"] = df_machines.to_dict(orient="records")
    logger.info(f"[fetch_rm_supplier] all_machines_for_Fg: {state['all_machines_for_Fg']}")


    if df_machines.empty:
        state["available_machines"] = []
        state["final_machine"] = []
        state["machine_flag"] = "No Machines Available"
        logger.info("[fetch_rm_supplier] No machines available for FG")
        return state
    state["available_machines"] = df_machines.to_dict(orient="records")
    logger.info(f"[fetch_rm_supplier] available_machines: {state['available_machines']}")

    # Filter for machine with highest IdealOutput
    if not df_machines.empty and "IdealOutput" in df_machines.columns:
        max_output_idx = df_machines["IdealOutput"].idxmax()
        final_machine = [df_machines.loc[max_output_idx].to_dict()]
        state["final_machine"] = final_machine
        logger.info(f"[fetch_rm_supplier] final_machine: {state['final_machine']}")
        state["machine_flag"] = "Machine Available"
        if final_machine and "IdealOutput" in final_machine[0]:
            ideal_output = final_machine[0]["IdealOutput"]
            try:
                ideal_output = float(ideal_output)
                if ideal_output > 0 and remaining_qty > 0:
                    time_hours = remaining_qty / ideal_output
                    time_days = math.ceil(time_hours / 24)
                    ist = pytz.timezone("Asia/Kolkata")
                    today_ist = datetime.now(ist)
                    dispatch_date = today_ist + timedelta(days=time_days)
                    state["dispatch_date"] = dispatch_date.strftime("%Y-%m-%d")
                    logger.info(f"[fetch_rm_supplier] Calculated dispatch date: {state['dispatch_date']}")
                else:
                    state["dispatch_date"] = "NA"
            except Exception as e:
                logger.error(f"Error calculating dispatch date: {e}")
                state["dispatch_date"] = "NA"
        else:
            state["dispatch_date"] = "NA"
    else:
        state["final_machine"] = []
        state["machine_flag"] = "No IdealOutput"
        logger.info("[fetch_rm_supplier] No IdealOutput column or empty DataFrame")
    

    return state


def final_report(state: FGState) -> FGState:
    log_state(state, "final_report")
    logger.info("[final_report] Start")
    # prompt = f"""
    # Generate a final dispatch readiness report with below data in tabluar format in detail report.
    # Input JSON: {state['input_json']}
    # Customer_name: {state['input_json']['customer_name']}
    # FG Available Qty: {state['fg_available_qty']}
    # FG_readiness_for_dispatch: {state['fg_is_ready']}
    # BOM: {state.get('bom_result', None)}
    # Available_RM: {state.get('rm_availability',None)}
    # Unavaialbe_RM: {state.get('rm_missing', None)}
    # Alternative_RM's_for_Unavailable_RM:{state.get('alternatives', None)}
    # Available_AlternateRM's:{state.get('alternatives_available_stock', None)}
    # Unavailable_AlternateRM's:{state.get('alternatives_unavailable_stock', None)}
    # Supplier_names:{state.get('rm_supplier_name', None)}
    # machine_allotment_status: {state.get('machine_flag', None)}
    # Machine_allotment: {state.get("final_machine",None)}
    # Dispatch_Date: {state.get("dispatch_date",None)}

    # with the above data u need to generate a Dispatch Report which should be a tabular report
    # follow the report structure
    # Customer_name:
    # Finished_Good:
    # Quantity:

    # Finished_Good_status: FG_readiness_for_dispatch

    # NOTE -**if Finished_Good_status is True then generate report with above rows else follow to add below structure aswell**
    # BOM:

    # Available_RM:

    # ** if all the RM in BOM are available then just generate the report else follow to add the below structure aswell**
    # Unavaliable_RM:
    # Alternative_RM_for_Unavailabe_RM:

    # Available_AlternativeRM:
    # Unavailable_Alternative_RM: ** if Any alternative RM are not available**

    # Suppliers_for_RawMaterials: supplier_names for missing RM from BOM 

    # give the machine allotment status and machine details if available
    # Machine_allotment_status: machine_flag
    # Machine_allotment: final_machine   

    # if final_machine is emtpy then do not include the machine_flag details in the report

    # create a final table with in the end with the final bom by including the alternative RM's.

    # with the above structure generate the report and company name on top center of the report "BLEND COLOURS" 
    # NOTE - "ONLY REPORT SHOULD BE IN THE OUTPUT DONOT INCLUDE ANY OTHER CHARACTERS OR ANYOTHER EXTRA CONTENT"
    # """
    # llm = ChatOpenAI(model="gpt-4o", openai_api_key="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")
    # response = llm.invoke([SystemMessage(content="You are a professional ETD report generator that creates clear, structured, tabular dispatch reports. Format everything precisely."),HumanMessage(content=prompt)])
    state["final_report"] = "generated"#response.content
    return state

#define workflow
workflow = StateGraph(FGState)

workflow.set_entry_point("check_fg_stock")
workflow.add_node("check_fg_stock", check_fg_stock)

workflow.add_conditional_edges(
    "check_fg_stock",
    check_dispatch_ready,
    {
        "ready": "generate_report",
        "not_ready": "get_bom"
    }
)

workflow.add_node("get_bom", get_bom)

workflow.add_node("rm_availablity_status",get_rm_availablity_status)

workflow.add_edge("get_bom", "rm_availablity_status")

workflow.add_conditional_edges(
    "rm_availablity_status",
    check_rm_stock,
    {
        "sufficient_rm": "machine_allotment",
        "missing_rm": "fetch_alternative_rm"
    }
)
workflow.add_node("machine_allotment", machine_allotment)
workflow.add_edge("machine_allotment", "generate_report")

workflow.add_node("fetch_alternative_rm", fetch_alternatives)
workflow.add_node("altRm_availablity_status",get_alterrm_stock_availability)
workflow.add_edge("fetch_alternative_rm", "altRm_availablity_status")

workflow.add_conditional_edges(
    "altRm_availablity_status",
    check_alterrm_stock,
    {
        "altrm_available": "machine_allotment",
        "altrm_unavailable": "fetch_rm_suppliers"
    }
)

workflow.add_node("fetch_rm_suppliers", fetch_rm_supplier)

workflow.add_edge("fetch_rm_suppliers","generate_report")

workflow.add_node("generate_report", final_report)

workflow.set_finish_point("generate_report")

graph = workflow.compile()

#generate the image
Image(graph.get_graph().draw_mermaid_png())

