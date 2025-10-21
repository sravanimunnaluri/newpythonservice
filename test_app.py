import pyodbc
import pandas as pd
import groq

# finding the alternative product for the given product based on the weightage >>>>>>>>>>>>>>>>>>>>
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=103.98.12.170,1508;"  
    "DATABASE=BCPL2024;"         
    "UID=ikonuser;"            
    "PWD=userikon;"            
    "TrustServerCertificate=yes;"
    "Encrypt=no;"
    "Connection Timeout=10;"
)

print("✅ Connected successfully!")

# LLM

# from groq import Groq

# client = Groq(
#     # This is the default and can be omitted
#   
# )

# # you are a helpful sql assistant who acan write the sql query and just give the sql query as output and databse is like there is only one table called AlternateProductsUsedInProduction with columns VoucherSeries,VoucherNo,BillOfMaterial,ActualBOMInputProduct,UsedProduct,Quantity. donot use LIMIT and give the sql query in single line
# chat_completion = client.chat.completions.create(
#     messages=[
#         {
#             "role": "system",
#             "content": """you are a helpful sql assistant who can write the sql query and just give the sql query as output and databse is like there is only one table called AlternateProductsUsedInProduction with columns VoucherSeries,VoucherNo,BillOfMaterial,ActualBOMInputProduct,UsedProduct,Quantity. 
            
#             the output query should contain:

#             UsedProduct
#             number_of_times_used - which is count 
#             QtyUsed
#             Weightage by QtyUsed'


            
#             donot use LIMIT and give the sql query in single line"""
#         },
#         {
#             "role": "user",
#             "content": "write a sql query to find the best alternate product can be used for ZANCARB 1T " ,
#         }
#     ],
#     model="llama-3.3-70b-versatile",
# )

# output =chat_completion.choices[0].message.content
# foutput = output[6:-3]
# print(output)

# df = pd.read_sql(output, conn)
# print(df)

# json_data = df.to_json(orient='records')

# print(json_data)


# chat_completion2 = client.chat.completions.create(
#     messages=[
#         {
#             "role": "system",
#             "content": f"""you are a helpful sql assistant who can analyse the pandas dataframe which is in the format of json and json is the output of the sql query which is executed on user input query on the database which is like there is only one table called AlternateProductsUsedInProduction with columns VoucherSeries,VoucherNo,BillOfMaterial,ActualBOMInputProduct,UsedProduct,Quantity and you need to analyse the json with respective to the user query and respond like human not the code.
                        
#                          steps to follow:
                          
#                            1- provided the {json_data}.
#                            2- according to the json_data find the usedproduct which is having more than 4% in weightage_by_qtyused.
#                            3- suggest the top 3 alternative products for the user asked RM material. """
#         },
#         {
#             "role": "user",
#             "content": f" user-query:  find the best alternate product can be used for ZANCARB 1T " ,
#         }
#     ],
#     model="llama-3.3-70b-versatile",
# )

# output2 =chat_completion2.choices[0].message.content

# print("final-output: ",output2)



# fetching the fg if available from inventory >>>>>>>>>>
# fg_product = "Blend Blown WHITE 2575 OS"

# sql_query = """select sum(isnull(receivedqty,0)-isnull(issuedqty,0)) StkBalance from StockLedger_Table where Product ='Blend Blown WHITE 2575 OS'  group by Product"""

# df2 = pd.read_sql(sql_query, conn)

# print(df2)


# BOM for FG >>>>>>>>>>

FG = "Blend Blown WHITE 2575 OS"

sql_query_bom = f"""select * from Master_BillsOfMaterial_Table where product ='{FG}'"""
df_bom = pd.read_sql(sql_query_bom, conn)

print(df_bom)


