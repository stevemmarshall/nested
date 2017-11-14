import math
import pprint
import copy

from python import ltr as pythonLtr
from python import domains as pythonBlast
from python import geneGraph

class Nester:
    #self.genes
    #self.nested
    def __init__(self, fasta_sequences):
        self.__findNestedTransposons(fasta_sequences)

    def getNested(self):
        return self.nested

    def getGenes(self):
        return self.genes

    def __findNestedTransposons(self, fasta_sequences):
        self.genes, self.nested = self.__getUnexpandedTransposons(fasta_sequences)
        
        for g in self.nested:
            self.nested[g] = self.__expandTransposons(self.nested[g])
    
    def __expandInterval(self, source, target):
        length = (source[1] - source[0])
        if source[0] <= target[0]:
            target[0] += length
        if source[0] <= target[1]:
            target[1] += length

        return target

    def __expandTransposons(self, nested): 
        for i in reversed(range(len(nested) - 1)):
            for j in range(i + 1, len(nested)):
                nested[j]['location'] = self.__expandInterval(nested[i]['location'], nested[j]['location'])
                for domain in nested[j]['features']['domains']:                    
                    domain['location'] = self.__expandInterval(nested[i]['location'], domain['location'])                
                nested[j]['features']['ppt'] = self.__expandInterval(nested[i]['location'], nested[j]['features']['ppt'])
                nested[j]['features']['pbs'] = self.__expandInterval(nested[i]['location'], nested[j]['features']['pbs'])
                
        return nested

    def __getUnexpandedTransposons(self, fasta_sequences):
        genes = self.__collectGeneInformation(fasta_sequences)

        #Save location for reconstruction
        nested = {}
        for g in genes:
            if math.isnan(genes[g]['best_pair']['location'][0]):
                nested[g] = []
            else:
                nested[g] = [genes[g]['best_pair']['evaluated']]

        #Crop
        cropped = False
        cropped_sequences = []
        for sequence in fasta_sequences:
            location = genes[sequence.id]['best_pair']['location']
            if not math.isnan(location[0]):
                cropped = True
                cropped_sequences.append(sequence[:(location[0] - 1)] + sequence[(location[1] + 1):])

        #Recursivelly call, if nesting is found
        if cropped:
            _, nested_cropped = self.__getUnexpandedTransposons(cropped_sequences)
            for g in nested_cropped:
                nested[g] += nested_cropped[g]
        
        return genes, nested
                
        

    def __collectGeneInformation(self, fasta_sequences):
        genes = pythonLtr.getGeneDict(fasta_sequences)
        genes = pythonLtr.runLtrFinder(genes)
        genes = pythonBlast.runBlastx(genes)

        genes = self.__findBestCandidate(genes)
        
        return genes

    def __findBestCandidate(self, genes):
        #evaluate pairs
        for g in genes:
            for ltr_pair in genes[g]['ltr_finder']:
                ltr_pair['evaluated'] = self.__evaluatePair(ltr_pair, genes[g])

        #find best candidate
        for g in genes:
            if not len(genes[g]['ltr_finder']):
                genes[g]['best_pair'] = {
                    'location': [float('nan'), float('nan')]
                }
            else:
                best_pair = max(genes[g]['ltr_finder'], key=lambda d: d['evaluated']['score'])
                genes[g]['best_pair'] = best_pair

        return genes


    def __evaluatePair(self, ltr_pair, gene):
        #g = geneGraph.GeneGraph(ltr_pair, gene['domains'])

        score = 0
        features = {
            'domains': [],
            'pbs': [float('nan'), float('nan')],
            'ppt': [float('nan'), float('nan')]
        }

        #Look for domains
        domains = gene['domains']
        for domain_type in domains:
            for domain in domains[domain_type]:
                domain_location = domain['location']
                if domain_location[0] > domain_location[1]:
                    domain_location = [domain_location[1], domain_location[0]]
                #found domain
                if domain_location[0] >= ltr_pair['location'][0] and domain_location[1] <= ltr_pair['location'][1]:
                    score += domain['score']
                    features['domains'].append(copy.deepcopy(domain))

        #Check PBS
        if not math.isnan(ltr_pair['pbs'][0]):
            score += 1000
            features['pbs'] = ltr_pair['pbs']

        #Check PPT
        if not math.isnan(ltr_pair['ppt'][0]):
            score += 1000
            features['ppt'] = ltr_pair['ppt']

        score /= float(ltr_pair['location'][1] - ltr_pair['location'][0])
        
        return {
            'location': copy.deepcopy(ltr_pair['location']),
            'score': score,
            'features': features
        }