from gurobipy import Model, GRB, quicksum

def milp_path_charging_gurobi(G,
                              start_node,
                              end_node,
                              initial_soc_percent=50,
                              target_soc_percent=90,
                              battery_kwh=60.0,          # 60kWh
                              driving_cost_rate=0.3,     # usd/kWh (行駛電費)
                              charging_power=80,         # kW
                              charging_cost_rate=0.3,    # usd/kWh (充電站電價)
                              energy_consumption_per_m=0.2 # Wh/m  => 0.2Wh/m
                             ):
    """
    在 NetworkX 圖 G 上，用Gurobi決定:
      1) 哪些邊(路徑)要走
      2) 每個節點的SOC (kWh)
      3) 在充電站充多少電 (kWh)

    輸出:
      - "status": Optimal / Infeasible / ...
      - "total_cost": 總成本
      - "edges_used": 哪些邊被選擇(路徑)
      - "soc": 每個節點的SOC
      - "charge": 每個節點充電量
    """

    # 將百分比轉成 kWh
    initial_soc_kwh = battery_kwh * (initial_soc_percent / 100.0)
    target_soc_kwh = battery_kwh * (target_soc_percent / 100.0)

    # 準備所有 "有邊"(u,v) 的集合 edges
    edges = []
    for (u, v) in G.edges():
        edges.append((u, v))
        if not G.is_directed():
            edges.append((v, u))
    edges = list(set(edges))  # 移除重複邊

    # 建立一個 dict 用來存 "行駛耗電(kWh)" & "行駛電費"
    edge_data = {}
    for (u, v) in edges:
        dist_m = G[u][v].get('length', 1.0)  # 預設1.0, 避免沒填
        wh = dist_m * energy_consumption_per_m  # (Wh)
        kwh = wh / 1000.0
        cost = kwh * driving_cost_rate
        edge_data[(u, v)] = {
            'drive_kwh': kwh,
            'drive_cost': cost
        }

    # 建立 Gurobi 模型
    model = Model("Path_Charging")

    # 1) 決策變數
    # x_{u,v}: 是否選擇邊 (u, v)
    x = model.addVars(edges, vtype=GRB.BINARY, name="x")

    # soc[u]: 抵達節點 u 的電量
    soc = model.addVars(G.nodes(), lb=0, ub=battery_kwh, vtype=GRB.CONTINUOUS, name="soc")

    # charge[u]: 在節點 u 充電量
    charge = model.addVars(G.nodes(), lb=0, vtype=GRB.CONTINUOUS, name="charge")

    # 限制非充電站充電量為 0
    for u in G.nodes():
        if not G.nodes[u].get('is_charging_station', False):
            charge[u].ub = 0

    # 2) 目標函式: 行駛電費 + 充電電費
    driving_cost = quicksum(edge_data[(u, v)]['drive_cost'] * x[u, v] for u, v in edges)
    charging_cost = quicksum(charging_cost_rate * charge[u] for u in G.nodes())
    model.setObjective(driving_cost + charging_cost, GRB.MINIMIZE)

    # 3) 約束條件
    # 3.1 流量/路徑約束
    for u in G.nodes():
        in_edges = [(i, j) for (i, j) in edges if j == u]
        out_edges = [(i, j) for (i, j) in edges if i == u]

        if u == start_node:
            model.addConstr(quicksum(x[e] for e in out_edges) == 1)
            model.addConstr(quicksum(x[e] for e in in_edges) == 0)
        elif u == end_node:
            model.addConstr(quicksum(x[e] for e in out_edges) == 0)
            model.addConstr(quicksum(x[e] for e in in_edges) == 1)
        else:
            model.addConstr(quicksum(x[e] for e in out_edges) == quicksum(x[e] for e in in_edges))

    # 3.2 SOC 遞推
    BigM = battery_kwh + 100
    for (u, v) in edges:
        drive_kwh = edge_data[(u, v)]['drive_kwh']
        model.addConstr(soc[v] >= soc[u] - drive_kwh + charge[v] - BigM * (1 - x[u, v]))

    # 3.3 初始 SOC
    model.addConstr(soc[start_node] == initial_soc_kwh)

    # 3.4 終點 SOC
    model.addConstr(soc[end_node] >= target_soc_kwh)

    # 4. 求解
    model.optimize()

    if model.status != GRB.OPTIMAL:
        print("No Optimal Solution, status =", model.status)
        return model.status, None, None, None, None

    total_cost = model.objVal
    edges_used = [(u, v) for u, v in edges if x[u, v].x > 0.5]
    soc_values = {u: soc[u].x for u in G.nodes()}
    charge_values = {u: charge[u].x for u in G.nodes()}

    return model.status, total_cost, edges_used, soc_values, charge_values


# 使用範例
if __name__ == "__main__":
    import networkx as nx

    # 讀取你的大圖
    graphml_file = "Taiwan.graphml"
    G = nx.read_graphml(graphml_file)

    # 起始與終點
    start_node = "-144866"
    end_node = "-212207"

    # 跑 MILP
    result = milp_path_charging_gurobi(
        G=G,
        start_node=start_node,
        end_node=end_node,
        initial_soc_percent=50,
        target_soc_percent=90,
        battery_kwh=60.0,
        driving_cost_rate=0.3,
        charging_power=80,
        charging_cost_rate=0.3,
        energy_consumption_per_m=0.2
    )

    status, total_cost, edges_used, soc_values, charge_values = result
    if status == GRB.OPTIMAL:
        print("Optimal solution found!")
        print("Total Cost =", total_cost)
        print("Edges used:", edges_used)
        print("SOC (kWh):", soc_values)
        print("Charge (kWh):", charge_values)
    else:
        print("No solution or not optimal. status =", status)
