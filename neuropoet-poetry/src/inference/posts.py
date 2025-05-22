from stressrnn import StressRNN
print(StressRNN().put_stress('Мы будем с тобой молиться за тебя Господу Богу нашему').replace('+', '\u0301'))