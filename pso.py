import numpy as np
import networkx as nx

graphml_file = "expanded_network_with_charging_test.graphml"
G = nx.read_graphml(graphml_file)

G = nx.relabel_nodes(G, lambda x: str(x))
start_node = "622617976"
end_node = "622617959"

if start_node not in G.nodes:
    raise ValueError(f"Start node {start_node} not found in the graph.")
if end_node not in G.nodes:
    raise ValueError(f"End node {end_node} not found in the graph.")

initial_soc = 20000  
min_soc = 10  
energy_consumption_per_km = 150  
charging_road_length = 200  
charging_cost_per_kWh = 0.2  
num_particles = 100  
num_iterations = 200  
omega = 0.7  
c1 = 1.5  
c2 = 1.5  

edges = list(G.edges(data=True))
num_edges = len(edges)

particles = np.random.uniform(0, 1, (num_particles, num_edges))  
velocities = np.zeros_like(particles)  
p_best = particles.copy()  
fitness = np.full(num_particles, np.inf)  
g_best = None  


def is_valid_path(particle):
    selected_edges = [(u, v) for i, (u, v, data) in enumerate(edges) if particle[i] > 0.5]
    subgraph = nx.DiGraph()
    subgraph.add_edges_from(selected_edges)

    if start_node not in subgraph.nodes or end_node not in subgraph.nodes:
        return False

    return nx.has_path(subgraph, start_node, end_node)

def fitness_function(particle):
    if not is_valid_path(particle):
        return np.inf

    soc = initial_soc
    total_cost = 0
    selected_edges = [(u, v, data) for i, (u, v, data) in enumerate(edges) if particle[i] > 0.5]

    for u, v, data in selected_edges:
        energy_consumption = data['length'] / 1000 * energy_consumption_per_km
        charging_gain = data['power'] * (charging_road_length / 10) if data.get('is_charging') else 0
        soc -= energy_consumption
        soc += charging_gain
        if soc < min_soc:
            return np.inf  
        if data.get('is_charging'):
            total_cost += charging_gain * charging_cost_per_kWh / 1000  

    return total_cost

# PSO
for t in range(num_iterations):
    for i in range(num_particles):
        fitness_value = fitness_function(particles[i])
        if fitness_value < fitness[i]:  
            p_best[i] = particles[i]
            fitness[i] = fitness_value

    g_best_index = np.argmin(fitness)
    if fitness[g_best_index] != np.inf:  
        g_best = p_best[g_best_index]

    for i in range(num_particles):
        r1, r2 = np.random.rand(2)
        velocities[i] = (
            omega * velocities[i] +
            c1 * r1 * (p_best[i] - particles[i]) +
            c2 * r2 * (g_best - particles[i])
        )
        particles[i] += velocities[i]
        particles[i] = np.clip(particles[i], 0, 1)  

final_solution = (g_best > 0.5).astype(int)
selected_edges = [(u, v, data) for i, (u, v, data) in enumerate(edges) if final_solution[i] == 1]

subgraph = nx.DiGraph()
subgraph.add_edges_from([(u, v) for u, v, data in selected_edges])

if nx.has_path(subgraph, start_node, end_node):
    print("The selected edges form a valid path.")
else:
    print("The selected edges do not form a valid path.")

# 計算總成本
total_cost = 0
for u, v, data in selected_edges:
    if data.get('is_charging'):
        total_cost += data['power'] * (charging_road_length / 10) * charging_cost_per_kWh / 1000
print(f"Total cost: {total_cost:.4f} USD")

# 輸出選中邊的 ID
selected_edge_ids = [data['id'] for u, v, data in selected_edges]
print("Selected edge IDs:", selected_edge_ids)
