import networkx as nx
import random

# 初始化參數
graphml_file = "Taiwan.graphml"
G = nx.read_graphml(graphml_file)

start_node = "-144866"
end_node = "-212207"
initial_soc = 90  # 起始電量 (%)
target_soc = 30  # 終點所需電量 (%)
maximum_power = 60000  # 電池最大容量 (Wh)
max_time = 3600 * 5  # 最大行駛時間 (秒)
energy_consumption_per_m = 0.2  # 每米耗電量 (Wh)
charging_station_power = 120  # 充電站功率 (kW)
K = 1000  # 需要的路徑數量

# Yen's Algorithm for K Shortest Paths
def yen_k_shortest_paths(G, source, target, K, weight="travel_time"):
    def dijkstra(G, source, target, weight):
        return nx.shortest_path(G, source=source, target=target, weight=weight)

    A = [dijkstra(G, source, target, weight)]
    B = []  # 儲存候選路徑

    for k in range(1, K):
        for i in range(len(A[k - 1]) - 1):
            spur_node = A[k - 1][i]
            root_path = A[k - 1][:i + 1]

            # 暫時移除 root_path 上的邊
            removed_edges = []
            for path in A:
                if len(path) > i and path[:i + 1] == root_path:
                    edge = (path[i], path[i + 1])
                    if G.has_edge(*edge):
                        removed_edges.append((edge, G[edge[0]][edge[1]][weight]))
                        G.remove_edge(*edge)

            # 計算 spur_path
            try:
                spur_path = nx.shortest_path(G, spur_node, target, weight=weight)
                total_path = root_path[:-1] + spur_path
                if total_path not in A and total_path not in B:
                    B.append(total_path)
            except nx.NetworkXNoPath:
                pass

            # 恢復移除的邊
            for edge, w in removed_edges:
                G.add_edge(edge[0], edge[1], **{weight: w})

        if not B:
            break

        # 選擇最短的候選路徑
        B.sort(key=lambda path: sum(G[path[i]][path[i + 1]][weight] for i in range(len(path) - 1)))
        A.append(B.pop(0))

    return A

# 篩選包含充電站的路徑
def filter_paths_with_charging_stations(G, paths):
    valid_paths = []
    for path in paths:
        if any(G.nodes[node].get("is_charging_station", False) for node in path):
            valid_paths.append(path)
    return valid_paths

# 對路徑進行充電模擬並驗證
def validate_paths_with_charging(G, paths, initial_soc, target_soc, max_time, max_power, energy_per_m):
    valid_paths = []

    for path in paths:
        soc = initial_soc
        time_spent = 0
        is_valid = True

        for u, v in zip(path[:-1], path[1:]):
            travel_time = G[u][v].get("travel_time")
            distance = G[u][v].get("length")
            energy_consumed = distance * energy_per_m / 1000  # kWh

            soc -= (energy_consumed / max_power) * 100
            time_spent += travel_time

            # 檢查是否需要充電
            if G.nodes[v].get("is_charging_station", False):
                charge_time = random.uniform(1800, 3600)  # 隨機充電時間
                charge_amount = min(
                    charge_time * charging_station_power, (100 - soc) * 0.01 * max_power
                )
                soc += charge_amount / max_power * 100
                time_spent += charge_time

            if soc < 10 or time_spent > max_time:
                is_valid = False
                break

        if is_valid and soc >= target_soc and time_spent <= max_time:
            valid_paths.append(path)

    return valid_paths

# 主程序
k_shortest_paths = yen_k_shortest_paths(G, start_node, end_node, K)
charging_paths = filter_paths_with_charging_stations(G, k_shortest_paths)
valid_paths = validate_paths_with_charging(G, charging_paths, initial_soc, target_soc, max_time, maximum_power, energy_consumption_per_m)

# 輸出結果
print(f"找到 {len(valid_paths)} 條符合要求的路徑：")
for i, path in enumerate(valid_paths):
    print(f"路徑 {i + 1}: {path}")
