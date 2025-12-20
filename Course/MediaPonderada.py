labs = 0.00
provas = 0.00

lab1 = 11

for i in range(4):
    while lab1 > 10:
        lab1 = float(input("Digite um valor: "))

    else:
        if i < 2:
            labs = labs + lab1
        else:
            provas = provas + lab1

media = (0.2 * (provas / 2)) + (0.8 * (provas / 2))

print(media)

if media > 6:
    print("Aprovado!")

else:
    print("Reprovado!")
