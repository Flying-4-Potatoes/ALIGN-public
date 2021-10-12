
#include "../PnRDB/datatype.h"
#include "PlacerIfc.h"
#include "Placer.h"
#include "../EA_placer/placement.h"

double ConstGraph::LAMBDA=1.;
double ConstGraph::GAMAR=30;
double ConstGraph::BETA=0.1;
double ConstGraph::SIGMA=1000;
double ConstGraph::PHI=0.05;
double ConstGraph::PI=0.05;
double ConstGraph::PII=1;

PlacerIfc::PlacerIfc(PnRDB::hierNode& currentNode, int numLayout, string opath, int effort, PnRDB::Drc_info& drcInfo, const PlacerHyperparameters& hyper, bool select_in_ILP = false) : _nodeVec( numLayout, currentNode) {
  ConstGraph::LAMBDA = hyper.LAMBDA;
  if (hyper.use_analytical_placer) {
    Placement EA_placer;
    //EA_placer.set_dummy_net_weight(dummy_init_weight,dummy_init_rate,dummy_init_weight);
    EA_placer.place(currentNode);
  } else {
    Placer curr_plc(_nodeVec,opath,effort,drcInfo,hyper, select_in_ILP);
  }
}
