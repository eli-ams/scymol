import csv

import numpy as np
import scipy.stats as stats
import matplotlib.pyplot
from typing import Union, List, Dict, Tuple, Optional
from logging_functions import print_to_log, log_function_call


class InstantaneousPropertiesClass:
    @log_function_call
    def __init__(self, filename: str) -> None:
        """
        Read the properties from an Instantaneous file (e.g., *.out) written by LAMMPS and organize it into data arrays.

        :param filename: The path to the file containing the data.
        :return: None
        :rtype: None

        Examples:
        How to use TrajectoriesClass to read and analyze trajectory data:

        ```python

        inst_props = InstantaneousPropertiesClass("nvt_instantaneous.out")
        inst_props.generate_statistical_data()
        print(inst_props.data)
        print(inst_props.statistical_data)
        inst_props.plot_properties('TimeStep', 'c_thermo_temp')
        ```
        """

        self.filename = filename
        self.data = {}
        self.read_avetime_dump_file()
        self.statistical_data = {}

    @log_function_call
    def read_avetime_dump_file(self) -> None:
        """
        Read the average time dump file and store the data in a dictionary.

        :return: None
        :rtype: None
        """

        with open(self.filename, "r") as file:
            for i, line in enumerate(file):
                split_line = line.replace("#", "").split()
                if i == 1:  # The second line contains the headers
                    headers = split_line  # Include "TimeStep" as well
                    for header in headers:
                        self.data[header] = []
                elif i > 1:  # The following lines contain the data
                    for j, item in enumerate(split_line):
                        self.data[headers[j]].append(float(item))

    @log_function_call
    def calculate_stats(
        self, property_name: str
    ) -> Union[List[float], List[Tuple[float, float]], str]:
        """
        Calculate statistical metrics for a given property in the data.

        :param property_name: The name of the property for which statistics are to be calculated.
        :return: A list containing statistical measures or an error message if the property is not found.
        :rtype: Union[List[float], List[Tuple[float, float]], str]
        """

        if property_name not in self.data:
            return f"Property {property_name} not found in data."

        data_array = np.array(self.data[property_name])

        if np.all(data_array == data_array[0]):  # Check if all values are identical
            return [
                data_array[0],
                0,
                0,
                (data_array[0], data_array[0]),
                0,
                data_array[0],
                data_array[0],
            ]

        # 1. Average
        average = np.mean(data_array)

        # 2. Standard Deviation
        std_dev = np.std(data_array, ddof=1)

        # 3. Standard Error
        std_err = stats.sem(data_array)

        # 4. Confidence Interval
        confidence_level = 0.95
        degrees_freedom = len(data_array) - 1
        confidence_interval = stats.t.interval(
            confidence_level, degrees_freedom, average, std_err
        )

        # 5. Coefficient of Variation
        coef_var = (std_dev / average) * 100

        # 6. Max value
        max_val = np.max(data_array)

        # 7. Min value
        min_val = np.min(data_array)

        return [
            average,
            std_dev,
            std_err,
            confidence_interval,
            coef_var,
            max_val,
            min_val,
        ]

    @log_function_call
    def plot_properties(self, property1: str, property2: str) -> Optional[str]:
        """
        Plot a scatter plot of two properties against each other.

        :param property1: The name of the first property to plot.
        :param property2: The name of the second property to plot.
        :return: An error message if either property is not found, otherwise None.
        :rtype: Optional[str]
        """

        if property1 not in self.data or property2 not in self.data:
            return f"Either {property1} or {property2} not found in data."

        x_data = self.data[property1]
        y_data = self.data[property2]

        matplotlib.pyplot.figure(figsize=(10, 6))
        matplotlib.pyplot.scatter(x_data, y_data, marker="o")
        matplotlib.pyplot.title(f"{property1} vs {property2}")
        matplotlib.pyplot.xlabel(property1)
        matplotlib.pyplot.ylabel(property2)
        matplotlib.pyplot.grid(True)
        matplotlib.pyplot.show()

    @log_function_call
    def all_properties_to_csv(self, csv_file: str) -> None:
        """
        Write all properties and their calculated statistics to a CSV file.

        :param csv_file: The path to the CSV file where data should be written.
        :return: None
        :rtype: None
        """

        csv_headers = [
            "Property",
            "Mean",
            "Standard Deviation",
            "Standard Error",
            "Confidence Interval Left",
            "Confidence Interval Right",
            "Coefficient of Variation",
            "Max",
            "Min",
        ]

        with open(csv_file, "w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(csv_headers)

            for key in list(self.data.keys()):
                stats = self.calculate_stats(key)

                if isinstance(stats[3], tuple):
                    left_ci, right_ci = stats[3]
                else:
                    left_ci, right_ci = stats[3], stats[3]

                row_data = stats[:3] + [left_ci, right_ci] + stats[4:]
                csv_writer.writerow([key] + row_data)

                # Store the statistical data in self.statistical_data dictionary
                self.statistical_data[key] = {
                    "Mean": stats[0],
                    "Standard Deviation": stats[1],
                    "Standard Error": stats[2],
                    "Confidence Interval Left": left_ci,
                    "Confidence Interval Right": right_ci,
                    "Coefficient of Variation": stats[4],
                    "Max": stats[5],
                    "Min": stats[6],
                }

    @log_function_call
    def generate_statistical_data(self) -> None:
        """
        Generate statistical data for all properties in the dataset.

        :return: None
        :rtype: None
        """

        for key in self.data.keys():
            stats = self.calculate_stats(key)
            if isinstance(stats, str):  # If the property is not found, skip
                continue

            # If the stats are valid, parse the confidence interval
            if isinstance(stats[3], tuple):
                left_ci, right_ci = stats[3]
            else:
                left_ci, right_ci = stats[3], stats[3]

            # Construct the statistical data dictionary
            self.statistical_data[key] = {
                "Mean": stats[0],
                "Standard Deviation": stats[1],
                "Standard Error": stats[2],
                "Confidence Interval Left": left_ci,
                "Confidence Interval Right": right_ci,
                "Coefficient of Variation": stats[4],
                "Max": stats[5],
                "Min": stats[6],
            }

    @log_function_call
    def generate_data(self, data: Dict[str, List[int]]) -> Dict[str, Dict[str, int]]:
        """
        Process the input data, where data is a dictionary with keys mapping to lists of integers.

        :param data: A dictionary where each key corresponds to a list of integers.
        :return: A dictionary with the same keys, where each key maps to a dictionary
                 containing the count of elements in the list and the sum of the elements.
        :rtype: Dict[str, Dict[str, int]]
        """

        result = {}
        for key, values in data.items():
            count = len(values)
            total = sum(values)
            result[key] = {"count": count, "total": total}
        return result
