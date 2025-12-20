nome = input("Digite o seu nome: ")
print("Olá", nome)

altura = float(input("Digite a sua altura: "))
peso = int(input("Digite o seu peso: "))

IMC = peso / (altura**2)
print("Seu IMC é %.2f" % IMC)
