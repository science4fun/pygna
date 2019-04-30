"""Docstring1
"""

import logging
import pickle
import numpy as np
import networkx as nx
import pygna.statistical_test as st
import pygna.statistical_comparison as sc
import pygna.diagnostic as diagnostic
import pygna.painter as paint
import pandas as pd
import scipy
import time
import scipy.linalg.interpolative
from copy import copy, deepcopy
import itertools
import tables
import seaborn as sns
from matplotlib import pyplot as plt


import yaml
import pandas as pd
import pygna.parser as parser
import pygna.output as output
import logging

class YamlConfig:
    def __init__(self):
        pass

    def write_config(self,data,filename):
        with open(filename, 'w') as outfile:
            yaml.dump(data, outfile, default_flow_style=True)

    def load_config(self,filename):
        with open(filename, 'r') as stream:
            try:
                config = (yaml.load(stream))
                return config

            except yaml.YAMLError as exc:
                return print(exc)





class Converter:

    def __init__(self, mapping_table_file='../../../primary_data/entrez_name.tsv',
                entrez_col="NCBI Gene ID",
                symbol_col="Approved symbol"):
        with open(mapping_table_file, "r") as f:
            self.map_table=pd.read_table(f)

        self.map_table=self.map_table.fillna("0")
        self.map_table["Approved symbol"]=self.map_table["Approved symbol"].str.upper()
        self.map_table["Synonyms"]=self.map_table["Synonyms"].str.upper()
        self.map_table["Previous symbols"]=self.map_table["Previous symbols"].str.upper()
        self.entrez_column=entrez_col
        self.symbol_column=symbol_col

    def entrez2symbol(self,geneset):
        unknown_counter=0
        geneset_symbol=[]
        for i in geneset:
            name=self.map_table[self.map_table[self.entrez_column]==int(i)][self.symbol_column].values.tolist()
            if len(name)>0:
                geneset_symbol.append(str(name[0]))
            else:
                unknown_counter+=1
                geneset_symbol.append("<"+i+">")
        if unknown_counter>0:
            logging.warning("%d/%d terms that couldn't be mapped" %(unknown_counter,len(geneset) ))
        return geneset_symbol

    def symbol2entrez(self, geneset):
        geneset_entrez=[]
        unknown_counter=0
        for i in geneset:
            i=i.upper()
            name=self.map_table[self.map_table[self.symbol_column].str.upper()==i][self.entrez_column].values.tolist()
            if len(name)>0:
                geneset_entrez.append(str(int(name[0])))
            else:

                if (self.map_table["Synonyms"].str.contains(i).any() or self.map_table["Previous symbols"].str.contains(i).any()) :

                    name=self.map_table[self.map_table["Synonyms"].str.match("(^|.*,\s)%s(, .*|$| $)" %i)].loc[:,self.entrez_column].values.tolist()
                    previous=self.map_table[self.map_table["Previous symbols"].str.match("(^|.*,\s)%s(,.*|$| $)" %i)].loc[:,self.entrez_column].values.tolist()
                    name=list(set(name).union(set(previous)))

                    if len(name)==1:
                        geneset_entrez.append(str(int(name[0])))
                    elif len(name)>1:
                        geneset_entrez.append(str(int(name[0])))
                        logging.warning("for gene %s there are multiple mapping sites: " %i + str(name))
                    else:
                        unknown_counter+=1
                        geneset_entrez.append("<"+i+">")
                else:
                    unknown_counter+=1
                    geneset_entrez.append("<"+i+">")

        if unknown_counter>0:
            logging.warning("%d/%d terms that couldn't be mapped" %(unknown_counter,len(geneset) ))

        return geneset_entrez


def convert_gmt(gmt_file:"gmt file to be converted",
                output_file:"output file",
                conversion: "e2s or s2e",
                converter_map_filename: "tsv table used to convert gene names" = '../../../primary_data/entrez_name.tsv' ,
                entrez_col: "name of the entrez column" = "NCBI Gene ID",
                symbol_col: "name of the symbol column" = "Approved symbol"):


    GMTparser=parser.GMTParser()
    genesets_dict=GMTparser.read(gmt_file,read_descriptor=True)
    print(genesets_dict)

    converter=Converter(converter_map_filename, entrez_col, symbol_col)

    if conversion=="e2s":
        for key, dict in genesets_dict.items():
            genesets_dict[key]["genes"]=converter.entrez2symbol(dict["genes"])

    elif conversion == "s2e":
        for key, dict in genesets_dict.items():
            genesets_dict[key]["genes"]=converter.symbol2entrez(dict["genes"])
    else:
        logging.error("conversion type not understood")

    output.print_GMT(genesets_dict, output_file)


def new_network(filename:"barabasi network file to be converted",
                output_file:"output file",
                int_type: "interaction type"):


    with open(output_file,"w") as f:
        f.write("# Gene1\t Gene2 \t interaction_type \n")


    for record in open(filename):
        if record.startswith('#'):
            continue

        fields = record.strip().split("\t")
        types=fields[2].split(";")


        if int_type in types:
            with open(output_file,"a") as f:
                f.write(fields[0]+"\t"+fields[1]+"\t"+int_type+"\n")



def csv2gmt(input_file:'input csv file',
                setname:'name of the set',
                output_file: 'output gmt file',
                name_column: 'column with the names'='Unnamed: 0',
                filter_column: 'column with the values to be filtered'= 'padj',
                alternative:'alternative to use for the filter, with less the filter is applied <threshold, otherwise >= threshold' ='less',
                threshold: 'threshold for the filter'=0.01,
                descriptor:'descriptor for the gmt file'=None):

    """
    This function converts a csv file to a gmt allowing to filter the elements 
    using the values of one of the columns. The user can specify the column used to 
    retrieve the name of the objects and the filter condition. 
    """

    if input_file.endswith('.csv'):
        with open(input_file,'r') as f:
            table=pd.read_csv(f)
    else:
        logging.error('only csv files supported')
    
    if descriptor==None:
        descriptor=input_file.split('/')[-1]
    
    threshold=float(threshold)

    gmt_dict={}
    gmt_dict[setname]={}
    gmt_dict[setname]['descriptor']=descriptor
    gmt_dict[setname]['genes']=[]

    try:
        if alternative=='less':
            geneset=table[table[filter_column]<threshold].loc[:,name_column].values.tolist()
        else:
            geneset=table[table[filter_column]>=threshold].loc[:,name_column].values.tolist()
    except:
        logging.error('error in filtering')

    logging.info('geneset='+str(geneset))
    gmt_dict[setname]['genes']=geneset

    if output_file.endswith('.gmt'):
        output.print_GMT(gmt_dict, output_file)
    else:
        logging.error('specify gmt output')