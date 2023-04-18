from pydriller import Repository

files_to_check = [
    'src/main/java/org/apache/commons/lang3/StringUtils.java'
]

# TODO: Integrar com o CK (para todo o repositório) para analisar cada commit do código de modo a compará-los.
# TODO: Contador para lembrar da ordem.

def main():
    print("Processing...")
    for commit in Repository('https://github.com/apache/commons-lang').traverse_commits():
        for file_name in files_to_check:
            with open('output.txt', 'w') as f:
                f.write("Filename: " + file_name + "\n")
                f.write("Commit Message: " + commit.msg)
    print("Done!")
    
if __name__ == "__main__":
    main()