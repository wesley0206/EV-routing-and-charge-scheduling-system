import random
import networkx as nx
import numpy as np

# 讀取圖形文件
graphml_file = "Taiwan.graphml"
G = nx.read_graphml(graphml_file)

# 參數設置
start_node = "-144866"
end_node = "-212207"
initial_soc = 80  # 起始電量 (百分比)
target_soc = 80  # 目標電量 (百分比)
maximum_power = 60000  # 電池最大容量 (Wh)
max_time = 3600 * 2  # 總時間為 2 小時
charging_cost_per_kWh_peak = 0.3  # 尖峰時段每千瓦時充電成本 (usd)
charging_cost_per_kWh_offpeak = 0.2  # 非尖峰時段每千瓦時充電成本 (usd)
energy_consumption_per_m = 0.2  # 每米耗電量 (Wh)
charging_station_power = 80  # kW (充電站功率)
power_track_power = 12 # kW
power_track_length = 200 # m

# 螞蟻群算法參數
num_ants = 300
iterations = 300
alpha = 4
beta = 4
rho = 0.1
Q = 100
min_pheromone = 1e-6  # 費洛蒙濃度下限

visited_nodes = {}


# 初始化費洛蒙
def initialize_pheromone(G):
    pheromone = {}
    for u, v in G.edges():
        pheromone[(u, v)] = 1.0
        if G.nodes[u].get('is_charging_station', False):
            pheromone[(u, 'charging')] = {0: 1.0, 15: 1.0, 30: 1.0, 45: 1.0, 60: 1.0}
    return pheromone

# 計算邊的距離
def calculate_distance(u, v):
    return G[u][v].get('length', 1)

# 計算能量消耗
def calculate_energy_consumption(u, v):
    return calculate_distance(u, v) * energy_consumption_per_m

# 計算行駛時間
def calculate_travel_time(u, v):
    return G[u][v].get('travel_time', 0)

def calculate_pt_energy_gain(u, v):
    return power_track_length / G[u][v].get('speed') * power_track_power / 3600

# 計算充電成本
def calculate_station_segmented_cost(start_time, duration):
    remaining_time = duration
    total_cost = 0
    charging_energy = 0

    while remaining_time > 0:
        if start_time < 1.5 * 3600:
            segment_time = min(remaining_time, 1.5 * 3600 - start_time)
            unit_cost = charging_cost_per_kWh_peak
        else:
            segment_time = remaining_time
            unit_cost = charging_cost_per_kWh_offpeak

        segment_energy = charging_station_power * segment_time / 3600
        segment_cost = segment_energy * unit_cost
        charging_energy += segment_energy * 1000
        total_cost += segment_cost

        remaining_time -= segment_time
        start_time += segment_time

    return total_cost, charging_energy

def heuristic(u, v, current_soc):
    energy_consumption = calculate_energy_consumption(u, v)
    travel_time = calculate_travel_time(u, v)
    visit_count = visited_nodes.get(v, 0)
    return 1.0 / (travel_time + visit_count * 10)

class Ant:
    def __init__(self, start_node, end_node):
        self.path = [start_node]
        self.soc = initial_soc
        self.time_spent = 0
        self.current_node = start_node
        self.end_node = end_node
        self.total_cost = 0
        self.stations_log = []

    def move(self, pheromone, alpha, beta):
        next_node = self.select_next_node(pheromone, alpha, beta)
        visited_nodes[next_node] = visited_nodes.get(next_node, 0) + 1
        self.path.append(next_node)
        self.current_node = next_node
        
        if G[self.path[-2]][self.path[-1]].get('is_charging', False):  # 如果是充電道路
            pt_charging = calculate_pt_energy_gain(self.path[-2], self.path[-1])
            energy_consumption = calculate_energy_consumption(self.path[-2], self.path[-1]) - pt_charging
            charging_cost = pt_charging * (charging_cost_per_kWh_peak if self.time_spent < 1.5 * 3600 else charging_cost_per_kWh_offpeak) / 1000
            self.total_cost += charging_cost  # 計入總成本
            self.soc = self.soc + (pt_charging / maximum_power) * 100
        else:  # 普通道路
            energy_consumption = calculate_energy_consumption(self.path[-2], self.path[-1])
            
        travel_time = calculate_travel_time(self.path[-2], self.path[-1])
        self.time_spent += travel_time
        self.soc -= energy_consumption / maximum_power * 100

        if G.nodes[next_node].get('is_charging_station', False):
            self.handle_charging_station(pheromone, alpha, beta)

    def handle_charging_station(self, pheromone, alpha, beta):
        charging_options = list(pheromone[(self.current_node, 'charging')].keys())
        probabilities = []
        for option in charging_options:
            pheromone_strength = pheromone[(self.current_node, 'charging')][option]
            projected_soc = self.soc + (option / 60) * charging_station_power * 1000 / maximum_power * 100
            heuristic_strength = 1.0 / (1 + abs(target_soc - projected_soc))
            probabilities.append((pheromone_strength ** alpha) * (heuristic_strength ** beta))

        total_prob = sum(probabilities)
        probabilities = [p / total_prob for p in probabilities] if total_prob > 0 else [1 / len(probabilities)] * len(probabilities)
        chosen_option = random.choices(charging_options, probabilities)[0]

        if chosen_option > 0:
            charging_time = chosen_option * 60
            charging_energy = charging_time * charging_station_power / 3600
            station_cost = charging_energy * (charging_cost_per_kWh_peak if self.time_spent < 1.5 * 3600 else charging_cost_per_kWh_offpeak)
            self.soc += charging_energy * 1000 / maximum_power * 100
            self.time_spent += charging_time
            self.total_cost += station_cost
            self.stations_log.append({
                "station": self.current_node,
                "charging_time": charging_time,
                "charging_energy": charging_energy,
                "cost": station_cost
            })

    def select_next_node(self, pheromone, alpha, beta):
        neighbors = list(G.neighbors(self.current_node))
        probabilities = []
        for neighbor in neighbors:
            pheromone_strength = pheromone.get((self.current_node, neighbor), min_pheromone)
            heuristic_strength = heuristic(self.current_node, neighbor, self.soc)
            probabilities.append((pheromone_strength ** alpha) * (heuristic_strength ** beta))

        total_prob = sum(probabilities)
        probabilities = [p / total_prob for p in probabilities]
        return random.choices(neighbors, probabilities)[0]

def run_aco():
    pheromone = initialize_pheromone(G)

    best_path = None
    best_cost = float('inf')
    best_log = []
    best_time = float('inf')
    final_soc = None

    for iteration in range(iterations):
        ants = [Ant(start_node, end_node) for _ in range(num_ants)]

        for ant in ants:
            while ant.current_node != end_node and ant.soc > 10 and ant.time_spent < max_time:
                ant.move(pheromone, alpha, beta)

            if ant.current_node == end_node and ant.soc >= target_soc:
                if ant.time_spent < best_time:
                    best_path = ant.path
                    best_cost = ant.total_cost
                    best_log = ant.stations_log
                    best_time = ant.time_spent
                    final_soc = ant.soc

        for ant in ants:
            if ant.current_node == end_node:
                #print(ant.path)
                for i in range(len(ant.path) - 1):
                    edge = (ant.path[i], ant.path[i + 1])
                    pheromone[edge] = max(pheromone[edge] + Q / ant.total_cost, min_pheromone)
                for log in ant.stations_log:
                    station = log['station']
                    charging_time = log['charging_time'] // 60
                    if charging_time in pheromone[(station, 'charging')]:
                        pheromone[(station, 'charging')][charging_time] = max(pheromone[(station, 'charging')][charging_time] + Q / ant.total_cost, min_pheromone)

        for edge in pheromone:
            if isinstance(pheromone[edge], dict):
                for option in pheromone[edge]:
                    pheromone[edge][option] = max(pheromone[edge][option] * (1 - rho), min_pheromone)
            else:
                pheromone[edge] = max(pheromone[edge] * (1 - rho), min_pheromone)

    return best_path, best_cost, best_log, best_time, final_soc

best_path, best_cost, best_log, best_time, final_soc = run_aco()
print("Path:", best_path)
print("Cost:", best_cost)
print("Stations Log:", best_log)
print("Total Time Spent:", best_time, "seconds")
print("Final SOC:", final_soc, "%")