import xml.etree.ElementTree as ET
import networkx as nx

# 載入 SUMO 的 .net.xml 文件
network_tree = ET.parse('Taiwan2.net.xml')  # 請替換為你的 SUMO 網路文件名稱
network_root = network_tree.getroot()


# 初始化有向圖
G = nx.DiGraph()


# 遍歷所有節點，並將其加入圖中
for node in network_root.findall('node'):
   node_id = node.get('id')
   x, y = float(node.get('x')), float(node.get('y'))
   G.add_node(node_id, pos=(x, y))  # 使用節點的座標作為屬性


# 遍歷所有邊，將其加入有向圖中
for edge in network_root.findall('edge'):
   # 排除內部邊
   if 'function' in edge.attrib and edge.get('function') == 'internal':
       continue


   edge_id = edge.get('id')
   from_node = edge.get('from')
   to_node = edge.get('to')
   length = float(edge.find('lane').get('length'))
   speed = float(edge.find('lane').get('speed'))
   travel_time = float(edge.find('lane').get('length')) / float(edge.find('lane').get('speed'))
  
   # 將邊添加到圖中，並加上長度和速度等屬性
   G.add_edge(from_node, to_node, id=edge_id, length=length, speed=speed, travel_time=travel_time, is_charging=False)


# 載入充電站文件並標記充電邊
charging_tree = ET.parse('power_track_add_Taiwan.xml')  # 請替換為你的充電站文件名稱
charging_root = charging_tree.getroot()


# 提取充電站資訊，並標記 NetworkX 圖中的相應邊
for station in charging_root.findall('chargingStation'):
   lane_id = station.get('lane')
   edge_id = lane_id.split('_')[0]  # 假設 edge_id 是 lane_id 去掉 "_0" 等後綴部分
  
   # 在 NetworkX 圖中找到對應的邊，並設置充電屬性
   for from_node, to_node, data in G.edges(data=True):
       if data['id'] == edge_id:
           data['is_charging'] = True
       
# 載入充電站文件並標記充電站
charging_tree = ET.parse('charging_stations_add_Taiwan.xml')  # 請替換為你的充電站文件名稱
charging_root = charging_tree.getroot()

# 提取充電站資訊，並標記 NetworkX 圖中的相應節點
for station in charging_root.findall('chargingStation'):
    lane_id = station.get('lane')
    edge_id = lane_id.split('_')[0]  # 假設 edge_id 是 lane_id 去掉 "_0" 等後綴部分
    start_pos = float(station.get('startPos'))

    # 找到與充電站匹配的節點
    for from_node, to_node, data in G.edges(data=True):
        if data['id'] == edge_id:
            # 將充電站屬性標記到目標節點上
            G.nodes[to_node]['is_charging_station'] = True
            G.nodes[to_node]['charging_station_id'] = station.get('id')
            break


# 圖構建完成，現在 G 是包含充電資訊的 NetworkX 有向圖
# 將圖保存為 GraphML 格式
largest_scc = max(nx.strongly_connected_components(G), key=len)
G_largest_scc = G.subgraph(largest_scc).copy()

# 輸出結果
print(f"Original Graph Nodes: {len(G.nodes)}")
print(f"Original Graph Edges: {len(G.edges)}")
print(f"Largest Strongly Connected Component Nodes: {len(G_largest_scc.nodes)}")
print(f"Largest Strongly Connected Component Edges: {len(G_largest_scc.edges)}")

# 保存結果為 GraphML 格式
nx.write_graphml(G_largest_scc, "Taiwan.graphml")
# 檢查是否強連通
if nx.is_strongly_connected(G_largest_scc):
    print("The graph is already strongly connected.")
else:
    print("The graph is not strongly connected.")
    components = list(nx.strongly_connected_components(G))
    print(f"Strongly connected components: {components}")

