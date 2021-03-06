import xlrd
import xlsxwriter
import copy
import os.path as path


class INNFormatter:
    def __init__(self, ifn, inns, kpps=None, ofn='', names=None, prefix=None, suffix=None):
        """
        Object that check values in .xlsx file with INN of organisations
        :param ifn: Name of file with organisations INN and name\n
        :param inns: List of column numbers INN\n
        :param kpps: List of column numbers CIO. Its should be associated with inns\n
        :param ofn: Name of output file\n
        :param names: List of column numbers
        """

        def generate_output_filename(out_fn):
            """
            check output filename: it should be .xlsx and filename not empty. If name is empty then output filename
            generated by name of input file\n
            :param out_fn: Name of output file\n
            :return: Name of output file. Format [Corrected]<out_fn|self._input_file_name>[.xlsx]
            """
            out_fn.translate(str.maketrans('', '', '?/\\<>|*:"'))
            if out_fn:
                if len(out_fn) > 5 and out_fn.endswith('.xlsx'):
                    return out_fn
                else:
                    return '{}.xlsx'.format(out_fn)
            else:
                return 'Corrected {}'.format(self._input_file_name)

        def generate_inn_kpp_dict(inn_list, kpp_list):
            """
            Associate INNs and CIOs from lists of INNs and CIOs\n
            :param inn_list: List of INNs\n
            :param kpp_list: List of CIOs\n
            :return: dict{inn1: cio1, inn2: cio2, ...}. innN from INNs, cioN from CIOs
            """
            if kpp_list is None:
                kpp_list = [None] * len(inn_list)
            else:
                kpp_list.extend([None] * (len(inn_list) - len(kpp_list)))
            inn_kpp = {i: k for i, k in zip(inn_list, kpp_list)}
            return inn_kpp

        def check_input_file(fn):
            """
            Check existance of .xlsx inputfile\n
            If file does not exist stop work with code 2 (winerror file not exist)
            :param fn: Name of input .xlsx file\n
            :return: TRUE if file exist\n
            """
            if path.isfile(fn):
                return fn
            else:
                exit(2)

        if suffix is None:
            suffix = []
        if prefix is None:
            prefix = []
        if names is None:
            names = []
        self._names = names
        self._cur_row_num = 0
        self._cur_in_values = None
        self._cur_out_values = None
        self._input_file_name = check_input_file(ifn)
        self._output_file_name = generate_output_filename(ofn)
        self._inn_kpp = generate_inn_kpp_dict(inns, kpps)
        self._sheet = xlrd.open_workbook(self._input_file_name).sheet_by_index(0)
        self._work_book = xlsxwriter.Workbook(self._output_file_name)
        self._outsheet = self._work_book.add_worksheet('Corrected')
        self._prefix = {int(x): y for x, y in zip(*[iter(prefix)] * 2)}
        self._suffix = {int(x): y for x, y in zip(*[iter(suffix)] * 2)}

    @staticmethod
    def check_inn(inn):
        """
        Check INN by checksum\n
        :param inn: string with INN\n
        :return: True if INN is correct, else False
        """
        if len(inn) not in (10, 12):
            return False

        def inn_csum(inn_str):
            k = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
            pairs = zip(k[11 - len(inn_str):], [int(x) for x in inn_str])
            res = str(sum([k * v for k, v in pairs]) % 11 % 10)
            return res

        if len(inn) == 10:
            return inn[-1] == inn_csum(inn[:-1])
        else:
            return inn[-2:] == inn_csum(inn[:-2]) + inn_csum(inn[:-1])

    def _reformat_cells_kpp_info(self, inn_clmn, kpp_clmn):
        """
        generated corrected values of INN and CIO if have information about location of CIO in sheet\n
        :param inn_clmn: number of INN column\n
        :param kpp_clmn: number of CIO column\n
        :return: new string values of INN and CIO
        """
        kpp_value = self._cur_in_values[kpp_clmn].value
        inn_value = self._cur_in_values[inn_clmn].value
        # TODO если указан КПП, то длина ИНН не должна превышать 10
        if kpp_value:
            new_inn = '{:0>10}'.format(int(inn_value))
            new_kpp = '{:0>9}'.format(int(kpp_value))
        else:
            new_inn = '{:0>12}'.format(int(inn_value))
            new_kpp = ''
            if new_inn.startswith('00'):
                new_inn = new_inn[2:]

        return new_inn, new_kpp

    def _reformat_cells_kpp_none(self, inn):
        """
        generated corrected values of INN if have no information about location of CIO in sheet\n
        :param inn: number of INN column\n
        :return: new string values of INN
        """
        inn_value = str(int(self._cur_in_values[inn].value))
        l = len(inn_value)
        if l in (9, 11):
            return '0{}'.format(inn_value), ''
        else:
            return inn_value, ''

    def correct_inn(self):
        """
        correct values and types all over the work sheet\n
        call function correct_row for every row in sheet\n
        after work close output .xlsx file
        :raise: Exception if something went wrong
        """
        with open('logs.txt', mode='w') as log, open('INN_errors.txt', mode='w') as err:
            try:
                log.write('"{}" OPEN\n'.format(self._output_file_name))
                for self._cur_in_values in self._sheet.get_rows():
                    error = False
                    try:
                        log.write('\nstart handle {} row\n'.format(self._cur_row_num + 1))
                        log.write('formatting INN-KPP start\n')
                        self._correct_types_in_row()
                        log.write('formatting INN-KPP end\n')
                        if self._names:
                            log.write('adding cells without special symbols start\n')
                            self._add_cells_in_row_without_spec()
                            log.write('adding cells without special symbols end\n')
                        if self._prefix:
                            log.write('adding cells with prefix start\n')
                            self._add_cells_in_row_with_prefix()
                            log.write('adding cells with prefix end\n')
                        if self._suffix:
                            log.write('adding cells with suffix start\n')
                            self._add_cells_in_row_with_suffix()
                            log.write('adding cells with suffix end\n')
                    except ValueError as e:
                        error = True
                        log.write('{}\n'.format(e))
                        err.write('{:>5}:\t{}\n'.format(self._cur_row_num + 1, e))
                    finally:
                        self._write_corected_row(error)
                        log.write('end handle {} row\n'.format(self._cur_row_num + 1))
            except Exception as e:
                log.write('can\'t format {} row {}: {}\n'.format(self._cur_row_num + 1, self._cur_in_values, e))
            finally:
                self._work_book.close()
                log.write('\n\n"{}" CLOSE\n'.format(self._output_file_name))

    def _change_cell_value(self, inn_clmn, kpp_clmn, new_inn, new_kpp=''):
        """
        change value of cells with number inn_clmn and kpp_clmn to new_inn and new_kpp respectively\n
        types of cell set to string\n
        :param inn_clmn: number of column with INN\n
        :param kpp_clmn: number of column with CIO\n
        :param new_inn: new string value of INN\n
        :param new_kpp: new string value of CIO
        """
        self._cur_out_values[inn_clmn].ctype = 1
        self._cur_out_values[inn_clmn].value = new_inn
        if kpp_clmn:
            self._cur_out_values[kpp_clmn].ctype = 1
            self._cur_out_values[kpp_clmn].value = new_kpp

    def _correct_types_in_row(self):
        """
        generate corrected row. Generate new INN and CIO value, change types of cells to string\n
        :raise: ValueError if INN is incorrect or inappropriate argument value (of correct type)
        """
        self._cur_out_values = copy.deepcopy(self._cur_in_values)
        for inn_clmn, kpp_clmn in self._inn_kpp.items():
            new_inn = self._cur_in_values[inn_clmn].value
            new_kpp = self._cur_in_values[kpp_clmn].value if kpp_clmn else ''
            try:
                if kpp_clmn:
                    new_inn, new_kpp = self._reformat_cells_kpp_info(inn_clmn, kpp_clmn)
                else:
                    new_inn, new_kpp = self._reformat_cells_kpp_none(inn_clmn)
                if not self.check_inn(new_inn):
                    raise ValueError('Wrong INN checksum in {} row: {}\n'
                                     'formatting INN-KPP end\n'.format(self._cur_row_num + 1, new_inn))
            finally:
                self._change_cell_value(inn_clmn, kpp_clmn, new_inn, new_kpp)

    def _write_corected_row(self, error):
        """
        Add corrected row in result sheet. Row with error writen red in output file\n
        :param error: whether or not there an error in row
        """
        start_cell = 'A{}'.format(self._cur_row_num + 1)
        row_values = [str(cell.value).translate(str.maketrans(';', ' ')) for cell in self._cur_out_values]
        row_format = self._work_book.add_format({'bold': True, 'font_color': 'red'}) \
            if error else self._work_book.add_format({'bold': False, 'font_color': 'black'})
        self._outsheet.set_column(0, len(row_values), 15)
        self._outsheet.write_row(start_cell, row_values, row_format)
        self._cur_row_num += 1

    def _add_cells_in_row_with_prefix(self):
        def _add_cell_in_row_with_prefix(col_from, prefix):
            new_cell = copy.deepcopy(self._cur_out_values[col_from])
            new_cell.ctype = 1
            new_cell.value = '{}{}'.format(prefix, new_cell.value)
            self._cur_out_values.append(new_cell)

        for col in self._prefix:
            _add_cell_in_row_with_prefix(col, self._prefix[col])

    def _add_cells_in_row_with_suffix(self):
        def _add_cell_in_row_with_prefix(col_from, suffix):
            new_cell = copy.deepcopy(self._cur_out_values[col_from])
            new_cell.ctype = 1
            new_cell.value = '{}{}'.format(suffix, new_cell.value)
            self._cur_out_values.append(new_cell)

        for col in self._suffix:
            _add_cell_in_row_with_prefix(col, self._suffix[col])

    def _add_cells_in_row_without_spec(self):
        def _add_cell_in_row_without_spec(col_from):
            """
            Copy cell value which will be used in names of output files into the end of row.
            Chars that can't used in filename removed from new cell value
            :param col_from: number of column with value to copy
            """
            new_cell = copy.deepcopy(self._cur_in_values[col_from])
            new_cell.ctype = 1
            new_cell.value = new_cell.value.translate(str.maketrans('', '', '?/\\<>,|*:"'))
            self._cur_out_values.append(new_cell)

        for name in self._names:
            _add_cell_in_row_without_spec(name)

# TODO переписать логгер с использованием декораторов и обернуть функции в этот декоратор
# TODO добавить прогрессбар
# TODO добавить возможность склеивания столбцов (а-ля join по ячейкам)
# TODO сделать GUI
