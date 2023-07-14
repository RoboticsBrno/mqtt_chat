import rich

if __name__ == "__main__":
    with open("log.txt", "r") as f:
        rich.print(f.read())
