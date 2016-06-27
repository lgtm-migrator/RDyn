import os
import networkx as nx
import math
import numpy as np
import random
import scipy.stats as stats

__author__ = 'Giulio Rossetti'
__license__ = "GPL"
__email__ = "giulio.rossetti@gmail.com"
__version__ = "0.1.0"


class RDyn(object):

    def __init__(self, size=1000, iterations=1000, avg_deg=6, sigma=.8,
                 lambdad=.15, alpha=2.5, paction=.5, prenewal=.1,
                 conductance=.7, new_node=.0, del_node=.0, max_evts=1):

        # set the network generator parameters
        self.size = size
        self.iterations = iterations
        self.avg_deg = avg_deg
        self.sigma = sigma
        self.lambdad = lambdad
        self.exponent = alpha
        self.paction = paction
        self.renewal = prenewal
        self.new_node = new_node
        self.del_node = del_node
        self.max_evts = max_evts

        # initialize communities data structures
        self.communities = {}
        self.node_to_com = []
        self.total_coms = 0
        self.performed_community_action = "START\n"
        self.conductance = conductance
        self.exp_node_degs = []

        # initialize the graph
        self.graph = nx.empty_graph(self.size)

        # initialize output files
        self.output_dir = "results/%s_%s_%s_%s_%s_%s_%s" % \
            (self.size, self.iterations, self.avg_deg, self.sigma, self.renewal, self.conductance, self.max_evts)
        os.mkdir(self.output_dir)
        self.out_interactions = open("%s/interactions.txt" % self.output_dir, "w")
        self.out_events = open("%s/events.txt" % self.output_dir, "w")
        self.stable = 0

    def get_assignation(self, community_sizes):

        degs = [(i, self.exp_node_degs[i]) for i in xrange(0, len(self.exp_node_degs))]

        for c in xrange(0, len(community_sizes)):
            self.communities[c] = []

        unassigned = []

        for n in degs:
            nid,  nd = n
            assigned = False
            for c in xrange(0, len(community_sizes)):
                c_size = community_sizes[c]
                c_taken = len(self.communities[c])
                if c_size/float(nd) >= self.sigma and c_taken < c_size:
                    self.communities[c].append(nid)
                    assigned = True
                    break
            if not assigned:
                unassigned.append(n)

        slots_available = [(k, (community_sizes[k] - len(self.communities[k]))) for k in xrange(0, len(community_sizes))
                           if (community_sizes[k] - len(self.communities[k])) > 0]

        if len(unassigned) > 0:
            for i in unassigned:
                for c in xrange(0, len(slots_available)):
                    cid, av = slots_available[c]
                    if av > 0:
                        self.communities[cid].append(i[0])
                        self.exp_node_degs[i[0]] = community_sizes[cid] - 1
                        slots_available[c] = (cid, av-1)
                        break

        ntc = {}
        for cid, nodes in self.communities.iteritems():
            for n in nodes:
                ntc[n] = cid

        nodes = ntc.keys()
        nodes.sort()

        for n in nodes:
            self.node_to_com.append(ntc[n])

    @staticmethod
    def truncated_power_law(alpha, maxv, minv=1):
        """

        :param maxv:
        :param minv:
        :param alpha:
        :return:
        :rtype: object
        """
        x = np.arange(1, maxv + 1, dtype='float')
        pmf = 1 / x ** alpha
        pmf /= pmf.sum()
        return stats.rv_discrete(values=(range(minv, maxv + 1), pmf))

    def add_node(self):
        nid = self.size
        self.graph.add_node(nid)
        cid = random.sample(self.communities.keys(), 1)[0]
        self.communities[cid].append(nid)
        self.node_to_com.append(cid)
        deg = random.sample(range(2, int((len(self.communities[cid])-1) +
                                  (len(self.communities[cid])-1)*(1-self.sigma))), 1)[0]
        if deg == 0:
            deg = 1
        self.exp_node_degs.append(deg)
        self.size += 1

    def remove_node(self, it, count):

        com_sel = [c for c, v in self.communities.iteritems() if len(v) > 3]
        if len(com_sel) > 0:
            cid = random.sample(com_sel, 1)[0]
            s = self.graph.subgraph(self.communities[cid])
            min_value = min(s.degree().itervalues())
            candidates = [k for k in s.degree() if s.degree()[k] == min_value]
            nid = random.sample(candidates, 1)[0]
            for e in self.graph.edges([nid]):
                count += 1
                self.out_interactions.write("%s\t%s\t-\t%s\t%s\n" % (it, count, e[0], e[1]))
                self.graph.remove_edge(e[0], e[1])

            self.exp_node_degs[nid] = 0
            self.node_to_com[nid] = -1
            nodes = set(self.communities[cid])
            self.communities[cid] = list(nodes - {nid})
            self.graph.remove_node(nid)

    def get_degree_sequence(self):
        """

        :return:

        :rtype: object
        """
        minx = float(self.avg_deg) / (2 ** (1 / (self.exponent - 1)))

        while True:
            exp_deg_dist = self.truncated_power_law(self.exponent, self.size, int(math.ceil(minx)))
            degs = list(exp_deg_dist.rvs(size=self.size))
            if nx.is_valid_degree_sequence(degs):
                return degs, int(minx)

    def clean_targets(self, candidates, exp_node_deg, n):
        res = {t: exp_node_deg[t] - self.graph.degree(t) for t in candidates if
               (exp_node_deg[t] - self.graph.degree(t)) > 0 and t != n}

        # PA selection on remaining slots
        if len(res) > 0:
            return res

        return {}

    def test_communities(self, cut):
        for c in self.communities.values():
            if len(c) == 0:
                return False

            s = self.graph.subgraph(c)
            comps = nx.number_connected_components(s)
            s_degs = s.degree()
            g_degs = self.graph.degree(c)

            # Conductance
            edge_across = sum([g_degs[n] - s_degs[n] for n in c])
            c_nodes_total_edges = s.number_of_edges() + edge_across
            nodes_total_edges = self.graph.number_of_edges() - s.number_of_edges()

            ratio = 0
            if edge_across > 0:
                ratio = float(edge_across)/min(c_nodes_total_edges, nodes_total_edges)

            if comps > 1 or ratio > cut:
                return False

        return True

    def generate_event(self, it):
        self.stable += 1

        options = ["M", "S"]

        evt_number = random.sample(range(1, self.max_evts+1), 1)[0]
        evs = np.random.choice(options, evt_number, p=[.5, .5], replace=True)
        chosen = []

        self.output_communities(it)
        if "START" in self.performed_community_action:
            self.out_events.write("%s:\t%s" % (it, self.performed_community_action))
        else:
            self.out_events.write("%s:\n%s" % (it, self.performed_community_action))

        self.performed_community_action = ""

        for p in evs:

            if p == "M":
                # Generate a single merge
                if len(self.communities) == 1:
                    continue

                candidates = list(set(self.communities.keys()) - set(chosen))

                # promote merging of small communities
                cl = [len(v) for c, v in self.communities.iteritems() if c in candidates]
                comd = 1-np.array(cl, dtype="float")/sum(cl)
                comd /= sum(comd)

                ids = []
                try:
                    ids = np.random.choice(candidates, 2, p=list(comd), replace=False)
                except:
                    continue

                # ids = random.sample(candidates, 2)
                chosen.extend(ids)

                for node in self.communities[ids[1]]:
                    self.node_to_com[node] = ids[0]

                self.performed_community_action = "%s MERGE\t%s\n" % (self.performed_community_action, ids)

                self.communities[ids[0]].extend(self.communities[ids[1]])
                del self.communities[ids[1]]

            else:
                # Generate a single splits
                if len(self.communities) == 1:
                    continue

                candidates = list(set(self.communities.keys()) - set(chosen))

                cl = [len(v) for c, v in self.communities.iteritems() if c in candidates]
                comd = np.array(cl, dtype="float")/sum(cl)

                try:
                    ids = np.random.choice(candidates, 1, p=list(comd), replace=False)
                except:
                    continue

                c_nodes = len(self.communities[ids[0]])
                if c_nodes > 6:
                    try:
                        size = random.sample(range(3, c_nodes-3), 1)[0]
                        first = random.sample(self.communities[ids[0]], size)
                    except:
                        continue
                    cid = max(self.communities.keys()) + 1
                    chosen.extend([ids[0], cid])

                    self.performed_community_action = "%s SPLIT\t%s\t%s\n" % \
                                                      (self.performed_community_action, ids[0], [ids[0], cid])
                    # adjusting max degree
                    for node in first:
                        self.node_to_com[node] = cid
                        if self.exp_node_degs[node] > (len(first)-1) * self.sigma:
                            self.exp_node_degs[node] = int((len(first)-1) + (len(first)-1) * (1-self.sigma))

                    self.communities[cid] = first
                    self.communities[ids[0]] = [ci for ci in self.communities[ids[0]] if ci not in first]

                    # adjusting max degree
                    for node in self.communities[ids[0]]:
                        if self.exp_node_degs[node] > (len(self.communities[ids[0]])-1) * self.sigma:
                            self.exp_node_degs[node] = int((len(self.communities[ids[0]])-1) +
                                                           (len(self.communities[ids[0]])-1) * (1-self.sigma))

        self.out_events.flush()
        return self.node_to_com, self.communities

    def output_communities(self, it):

        self.total_coms = len(self.communities)
        out = open("%s/communities-%s.txt" % (self.output_dir, it), "w")
        for c, v in self.communities.iteritems():
            out.write("%s\t%s\n" % (c, v))
        out.flush()
        out.close()

        outg = open("%s/graph-%s.txt" % (self.output_dir, it), "w")
        for e in self.graph.edges():
            outg.write("%s\t%s\n" % (e[0], e[1]))
        outg.flush()
        outg.close()

    def get_community_size_distribution(self, mins=3):
        cv, nc = 0, 2
        cms = []

        nc += 2
        com_s = self.truncated_power_law(2, self.size/self.avg_deg, mins)

        exp_com_s = com_s.rvs(size=self.size)

        # complete coverage
        while cv <= 1:

            cms = random.sample(exp_com_s, nc)
            cv = float(sum(cms)) / self.size
            nc += 1

        while True:
            if sum(cms) <= self.size:
                break

            for cm in xrange(-1, -len(cms), -1):
                if sum(cms) <= self.size:
                    break
                elif sum(cms) > self.size and cms[cm] > mins:
                    cms[cm] -= 1

        return sorted(cms, reverse=True)

    def execute(self):
        """

        :return:
        """
        if self.size < 1000:
            print "Minimum network size: 1000 nodes"
            exit(0)

        # generate pawerlaw degree sequence
        self.exp_node_degs, mind = self.get_degree_sequence()

        # generate community size dist
        exp_com_s = self.get_community_size_distribution(mins=mind+1)

        # assign node to community
        self.get_assignation(exp_com_s)

        self.total_coms = len(self.communities)

        count = 0
        # main loop (iteration)
        for it in xrange(0, self.iterations):

            # community check and event generation
            if it > 0 and self.test_communities(self.conductance):
                self.node_to_com, self.communities = self.generate_event(it)

            # node removal
            ar = random.random()
            if ar < self.del_node:
                self.remove_node(it, count)
                print "Node removed: ", self.graph.number_of_nodes()

            # node addition
            ar = random.random()
            if ar < self.new_node:
                self.add_node()
                print "New Node: ", self.graph.number_of_nodes()

            self.out_interactions.flush()

            nodes = self.graph.nodes()
            random.shuffle(nodes)

            # inner loop (nodes)
            for n in nodes:

                # discard deleted nodes
                if self.node_to_com[n] == -1:
                    continue

                # check for decayed edges
                nn = nx.all_neighbors(self.graph, n)

                removal = []
                for n1 in nn:
                    delay = self.graph.get_edge_data(n, n1)['d']
                    if delay == it:
                        removal.append(n1)

                # removal phase
                for n1 in removal:
                    r = random.random()

                    # edge renewal phase
                    # check for intra/inter renewal thresholds
                    if r <= self.renewal and self.node_to_com[n1] == self.node_to_com[n]\
                            or r > self.renewal and self.node_to_com[n1] != self.node_to_com[n]:

                        # Exponential decay
                        timeout = (it + 1) + int(random.expovariate(self.lambdad))
                        self.graph.edge[n][n1]["d"] = timeout

                    else:
                        # edge to be removed
                        self.out_interactions.write("%s\t%s\t-\t%s\t%s\n" % (it, count, n, n1))
                        self.graph.remove_edge(n, n1)

                if self.graph.degree(n) >= self.exp_node_degs[n]:
                    continue

                # decide if the node is active during this iteration
                action = random.random()

                # the node has not yet reached it expected degree and it acts in this round
                if self.graph.degree(n) < self.exp_node_degs[n] and (action <= self.paction or it == 0):

                    com_nodes = set(self.communities[self.node_to_com[n]])

                    # probability for intra/inter community edges
                    r = random.random()

                    # check if at least sigma% of the node link are within the community
                    s = self.graph.subgraph(self.communities[self.node_to_com[n]])
                    d = s.degree(n)

                    # Intra-community edge
                    if d < len(com_nodes) - 1 and r <= self.sigma:
                        n_neigh = set(s.neighbors(n))

                        random.shuffle(list(n_neigh))
                        target = None

                        # selecting target node
                        candidates = {j: (self.exp_node_degs[j] - self.graph.degree(j)) for j in s.nodes()
                                      if (self.exp_node_degs[j] - self.graph.degree(j)) > 0 and j != n}

                        if len(candidates) > 0:
                            try:
                                target = random.sample(candidates, 1)[0]
                            except:
                                continue

                        # Interaction Exponential decay
                        timeout = (it + 1) + int(random.expovariate(self.lambdad))

                        # Edge insertion
                        if target is not None and not self.graph.has_edge(n, target) and target != n:
                            self.graph.add_edge(n, target, {"d": timeout})
                            count += 1
                            self.out_interactions.write("%s\t%s\t+\t%s\t%s\n" % (it, count, n, target))
                        else:
                            continue

                    # inter-community edges
                    elif r > self.sigma and \
                            self.exp_node_degs[n]-d < (1-self.sigma) * len(s.nodes()):

                        # randomly identifying a target community
                        try:
                            cid = random.sample(set(self.communities.keys()) - {self.node_to_com[n]}, 1)[0]
                        except:
                            continue

                        s = self.graph.subgraph(self.communities[cid])

                        # check for available nodes within the identified community
                        candidates = {j: (self.exp_node_degs[j] - self.graph.degree(j)) for j in s.nodes()
                                      if (self.exp_node_degs[j] - self.graph.degree(j)) > 0 and j != n}

                        # PA selection on available community nodes
                        if len(candidates) > 0:
                            candidatesp = np.array(candidates.values(), dtype='float') / sum(candidates.values())
                            target = np.random.choice(candidates.keys(), 1, list(candidatesp))[0]

                            if self.graph.has_node(target) and not self.graph.has_edge(n, target):

                                # Interaction exponential decay
                                timeout = (it + 1) + int(random.expovariate(self.lambdad))
                                self.graph.add_edge(n, target, {"d": timeout})
                                count += 1
                                self.out_interactions.write("%s\t%s\t+\t%s\t%s\n" % (it, count, n, target))

        self.output_communities(self.iterations)
        self.out_events.write("%s\n\t%s\n" % (self.iterations, self.performed_community_action))
        self.out_interactions.flush()
        self.out_interactions.close()
        self.out_events.flush()
        self.out_events.close()
        return self.stable
