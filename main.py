from typer import Typer

app = Typer()


@app.command()
def main():
    print("Hello from yoto-dev-tools!")


if __name__ == "__main__":
    app()
