import os

def replace_currency(path):
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Routes replacements
    code = code.replace("only ${remaining:.2f}", "only AED {remaining:.2f}")
    code = code.replace("${total_inv:.2f}", "AED {total_inv:.2f}")
    code = code.replace("${total_pay:.2f}", "AED {total_pay:.2f}")
    code = code.replace("${balance:.2f}", "AED {balance:.2f}")
    code = code.replace("${inv_amt:.2f}", "AED {inv_amt:.2f}")
    code = code.replace("${pay_amt:.2f}", "AED {pay_amt:.2f}")
    code = code.replace("${inv:.2f}", "AED {inv:.2f}")
    code = code.replace("${pay:.2f}", "AED {pay:.2f}")
    code = code.replace("${bal:.2f}", "AED {bal:.2f}")
    code = code.replace("${total_balance:.2f}", "AED {total_balance:.2f}")
    code = code.replace("${data[\"tot_inv\"]:.2f}", "AED {data[\"tot_inv\"]:.2f}")
    code = code.replace("${data[\"tot_pay\"]:.2f}", "AED {data[\"tot_pay\"]:.2f}")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)

if __name__ == '__main__':
    replace_currency('d:/Webapp/routes.py')
    print("Currency replaced in routes.py")
