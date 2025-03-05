def candela():
    candelita=0
    def subcandela():
        nonlocal candelita
        candelita=1
    subcandela()
    print(candelita)
candela()