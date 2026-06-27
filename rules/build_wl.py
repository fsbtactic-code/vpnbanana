import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_hosts(path):
    with open(path, encoding="utf-8") as f:
        raw = [l.strip().lower() for l in f]
    return sorted({h for h in raw if h and not h.startswith("#") and "." in h and " " not in h})


def apex(h):
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def main():
    src = os.path.join(HERE, "whitelist-src.txt")
    hosts = load_hosts(src)
    apexes = sorted({apex(h) for h in hosts})
    exact = sorted(set(hosts) | set(apexes))
    suffix = sorted({"." + a for a in apexes})
    print(f"hosts={len(hosts)} apexes={len(apexes)} exact={len(exact)} suffix={len(suffix)}")


    ruleset = {"version": 2, "rules": [{"domain": exact, "domain_suffix": suffix}]}
    with open(os.path.join(HERE, "ru-whitelist.json"), "w", encoding="utf-8") as f:
        json.dump(ruleset, f, ensure_ascii=False, indent=0)


    lines = ["payload:"]
    for a in apexes:
        lines.append(f"  - '+.{a}'")
    with open(os.path.join(HERE, "ru-whitelist-clash.yaml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


    with open(os.path.join(HERE, "ru-whitelist.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(exact) + "\n")

    print("wrote ru-whitelist.json / ru-whitelist-clash.yaml / ru-whitelist.txt")


if __name__ == "__main__":
    main()
