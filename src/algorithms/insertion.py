def insertion_sort(lista):
  for i in range(1, len(lista)):
    estrut = lista[i]
    for j in range(i - 1, -1, -1):
      if lista[j] > estrut:
        lista[j], lista[j + 1] = lista[j + 1], lista[j]
      else:
        lista[j +1] = estrut
        break
  return lista

lista = [3,5,7,3,8,9]
print( insertion_sort(lista))