def selection(lista):
  array=len(lista)
  for i in range(array):
    min = i
    for j in range(i + 1, array):
      if lista[j] < lista[min]:
        min = j
    lista[i], lista[min] = lista[min], lista[i]
  return lista
