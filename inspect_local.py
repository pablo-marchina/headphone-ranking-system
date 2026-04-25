import os

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoeq_repo", "measurements")
print("Reviewers em autoeq_repo/measurements/:\n")
for item in sorted(os.listdir(root)):
    path = os.path.join(root, item)
    if os.path.isdir(path):
        sub = os.listdir(path)
        print(f"  {item}  ({len(sub)} itens na raiz)")