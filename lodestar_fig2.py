import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Patch

# ----------------------------
# Build fraud ring network
# ----------------------------
G = nx.Graph()

# Entities
dmes = ["DME1", "DME2", "DME3", "DME4"]
providers = ["ProviderA", "ProviderB"]
ip_block = "Shared_IP_Block"
mailing_address = "Mailing_Address_X"
beneficiaries = ["Beneficiary1", "Beneficiary2", "Beneficiary3"]

# Add nodes with categories
for d in dmes:
    G.add_node(d, role="DME")
for p in providers:
    G.add_node(p, role="Provider")
G.add_node(ip_block, role="IP")
G.add_node(mailing_address, role="Address")
for b in beneficiaries:
    G.add_node(b, role="Beneficiary")

# Edges
G.add_edges_from([
    ("DME1", "ProviderA"),
    ("DME2", "ProviderA"),
    ("DME3", "ProviderB"),
    ("DME4", "ProviderB"),
    ("DME1", ip_block),
    ("DME2", ip_block),
    ("DME3", ip_block),
    ("DME4", ip_block),
    ("DME1", mailing_address),
    ("DME2", mailing_address),
    ("DME3", mailing_address),
    ("DME4", mailing_address),
    ("ProviderA", "Beneficiary1"),
    ("ProviderA", "Beneficiary2"),
    ("ProviderB", "Beneficiary2"),
    ("ProviderB", "Beneficiary3"),
])

# ----------------------------
# Draw with different shapes
# ----------------------------
pos = nx.spring_layout(G, seed=42)

role_styles = {
    "DME": {"color": "skyblue", "shape": "s"},       # square
    "Provider": {"color": "lightgreen", "shape": "^"},# triangle
    "IP": {"color": "orange", "shape": "D"},         # diamond
    "Address": {"color": "violet", "shape": "h"},    # hexagon
    "Beneficiary": {"color": "salmon", "shape": "o"} # circle
}

plt.figure(figsize=(10, 8))

# Draw edges first
nx.draw_networkx_edges(G, pos, edge_color="gray")

# Draw nodes by role
for role, style in role_styles.items():
    nodelist = [n for n, d in G.nodes(data=True) if d["role"] == role]
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=nodelist,
        node_color=style["color"],
        node_shape=style["shape"],
        node_size=1800,
        label=role
    )

# Draw labels
nx.draw_networkx_labels(G, pos, font_size=9, font_weight="bold")

# Legend
legend_handles = [
    Patch(facecolor=style["color"], label=role) for role, style in role_styles.items()
]
plt.legend(handles=legend_handles, loc="upper left", title="Entity Types")

plt.title("Fraud Ring Network with Meaningful Shapes", fontsize=14, weight="bold")
plt.axis("off")
plt.show()
