import math
import pulp

def generate_time_slices(current_time, stop_duration_minutes):
    """
    根據現在時刻與停留總分鐘數，自動切分出對應的時間片 (time slots)，
    並給出每個 time slot 的電價。

    需求：09:00~10:00 尖峰 (0.3), 10:00~11:00 離峰 (0.2)
    - current_time: 以 "HH:MM" 形式，如 "09:15"
    - stop_duration_minutes: e.g. 50
    回傳:
      - prices: list of (price) for each discrete slot
      - delta_t: 時間片長(小時)
      - T: 時間片數
    """
    # 1. 解析 current_time => 09:15 => hour=9, minute=15
    start_total_minutes = 9*60 + current_time/60  # e.g. 9*60+15=555

    # 2. 計算 "結束時間 (總分鐘數)"
    end_total_minutes = start_total_minutes + stop_duration_minutes  # e.g. 555+50=605 => 10:05

    # 這邊用 "5 分鐘" 為離散單位 (自行調整)
    slot_length_minutes = 5
    delta_t_hours = slot_length_minutes / 60  # => 5/60=0.0833小時

    # 3. 依序切出一個個 5 分鐘區塊, 判斷它落在哪個電價區
    prices = []
    current_min = start_total_minutes
    while current_min < end_total_minutes:
        # 這個 slot 結束時刻
        next_min = current_min + slot_length_minutes
        if next_min > end_total_minutes:
            # 最後一段不滿 5 分鐘 => 也可做特別處理
            # 這裡簡化: 當作整段5分鐘, 其實會多計一點time
            next_min = end_total_minutes

        # 判斷電價: 
        #   09:00~10:00 => total_minutes in [540, 600) => price=0.3
        #   10:00~11:00 => total_minutes in [600, 660) => price=0.2
        # 先以當下 slot 開始時間為基準 (或中間點亦可)
        if current_min < 600:
            price = 0.3  # 尖峰
        else:
            price = 0.2  # 離峰

        prices.append(price)

        current_min = next_min

    T = len(prices)  # time slot 數量
    return prices, delta_t_hours, T

def v2g_milp_optimize(current_time, stop_duration_minutes, initial_soc, final_soc,):
    """
    用 MILP 做 V2G 最佳化, 類似前面範例.
    """
    if stop_duration_minutes == 0:
        return 'Feasible',0,0
    battery_kwh = 60
    max_charge_power = 80
    max_discharge_power = 50
    prices, delta_t_hours, T = generate_time_slices(current_time, stop_duration_minutes)
    T = len(prices)

    model = pulp.LpProblem("V2G_Optimization", pulp.LpMinimize)
    # p[t]: -max_discharge_power <= p[t] <= max_charge_power
    p = [
        pulp.LpVariable(f"p_{t}",
                        lowBound=-max_discharge_power,
                        upBound= max_charge_power,
                        cat=pulp.LpContinuous) for t in range(T)
    ]
    # soc[t]: 0~100
    soc = [
        pulp.LpVariable(f"soc_{t}",
                        lowBound=0,
                        upBound=100,
                        cat=pulp.LpContinuous) for t in range(T+1)
    ]

    # 目標函數
    total_cost = 0
    for t in range(T):
        # p[t]>0 => 充電 => cost>0
        # p[t]<0 => 放電 => cost<0 => 代表收益
        total_cost += prices[t] * p[t] * delta_t_hours
    model += total_cost

    # SOC遞推
    for t in range(T):
        model += soc[t+1] == soc[t] + (p[t]*delta_t_hours/battery_kwh)*100

    # 初始/最終
    model += soc[0] == initial_soc
    model += soc[T] == final_soc

    # 求解
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    status = pulp.LpStatus[model.status]
    p_opt = [p[t].varValue for t in range(T)]
    soc_opt = [soc[t].varValue for t in range(T+1)]
    total_cost_val = pulp.value(model.objective)
    
    return status, total_cost_val, final_soc-initial_soc

    """return {
        "status": status,
        "total_cost": total_cost_val,
        "p": p_opt,
        "soc": soc_opt
    }"""

if __name__ == "__main__":
    # 假設使用者說: 我現在是09:15, 要停留 50 分鐘, initial_soc=50%, final_soc=80%
    # 呼叫 V2G MILP
    result = v2g_milp_optimize(
        1800,
        0,
        initial_soc=20,
        final_soc=90,
    )

    print(result)
    '''print("status:", result["status"])
    print("total_cost:", result["total_cost"])
    print("p:", result["p"])
    print("soc:", result["soc"])'''
