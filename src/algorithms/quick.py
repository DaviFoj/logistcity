def quick_sort(numbers):
  length= len(numbers)
  if length <= 1:
    return numbers
  
  pivot = numbers.pop()
  high, low= [], []
  for number in numbers:
    if number > pivot:
      high.append(number)
    else:
      low.append(number)
  return quick_sort(low) + [pivot] + quick_sort(high)

number_lista= [2, 30, 44, 7, 22]
print(quick_sort(number_lista))
