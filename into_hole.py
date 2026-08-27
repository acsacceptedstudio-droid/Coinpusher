import numpy as np
from fastapi import FastAPI,Path
from typing import Optional
app=FastAPI()
#預設每個洞的金額
hl_num_mony = np.full([12,2],50)
hl_num_mony[:,0] = np.arange(1,13)


#預設jpc洞
@app.post("/jpc_num/{jpc_num}")
async def set_jpc_num(jpc_num: int = Path(..., ge=1, le=12)):
    hl_num_mony[jpc_num-1,1]=0
    return {"message": f"第 {jpc_num} 洞已設為 JPC 洞", "amount":0 }


#進洞
@app.post("/into_hl_num/{into_hl_num}")
async def Into_hl_num(into_hl_num: int = Path(..., ge=1, le=12)):
    match hl_num_mony[into_hl_num-1,1]:
            case 50:
                hl_num_mony[into_hl_num-1,1]=80
                return {"message": f"第 {into_hl_num} 洞已設為 80", "give_money": 50}
            case 80:
                hl_num_mony[into_hl_num-1,1]=0
                return {"message": f"第 {into_hl_num} 洞已設為 jpc", "give_money": 80}
            case 0:
                hl_num_mony[into_hl_num-1,1]=50
                return {"message": f"第 {into_hl_num} 洞已設為 50", "give_money": 0}
