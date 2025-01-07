import networkx as nx

# 初始化參數
graphml_file = "Taiwan.graphml"
G = nx.read_graphml(graphml_file)

start_node = "-144866"
end_node = "-212207"
K = 500  # 需要的路徑數量

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

# 主程序
k_shortest_paths = yen_k_shortest_paths(G, start_node, end_node, K)
charging_paths = filter_paths_with_charging_stations(G, k_shortest_paths)

# 輸出結果
print(f"找到 {len(charging_paths)} 條經過充電站的路徑：")
for i, path in enumerate(charging_paths):
    print(f"路徑 {i + 1}: {path}")
